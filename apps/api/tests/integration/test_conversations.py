"""API de conversas com SSE: resposta citada, recusa, limites, idempotência e cancelamento.

FR-1 a FR-4, FR-9, FR-14, FR-17, FR-18, NFR-6, NFR-11 e NFR-13, seções 6.4, 7.1, 10.3, 10.4 e
12 do SDD. O `TestClient` chama a API real com o adaptador `fake`, e `_use` troca o
`get_qa_workflow` por um `QaWorkflow` com o `FakeChatProvider` roteirizado no teste, o
embedding `_Embeddings` e a busca `_Search`, que devolve chunks escritos à mão: a busca contra
o pgvector fica em `test_retrieval.py`. Os testes de desconexão falam ASGI direto para mandar
`http.disconnect` no meio do fluxo. `_delete_guest` apaga a chave de convidado, e as conversas
caem em cascata. Outros arquivos importam daqui os helpers de conversa. Precisa de PostgreSQL
com pgvector local (`migrated_database`); sem ele pula, e com `REQUIRE_INTEGRATION_DB=1` falha.
"""

import asyncio
import json
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.adapters.fake_chat import FakeChatProvider
from app.core.container import get_clock, get_feedback_sink, get_qa_workflow, get_settings
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import bucket_key, fixed_window_start, hash_session_secret
from app.domain.questions import (
    DIAGNOSTICS_IP_PURPOSE,
    DIAGNOSTICS_WINDOW,
    HEALTH_MESSAGE_MARKER,
    QUESTION_GUEST_KEY_PURPOSE,
    QUESTION_MEMBER_PURPOSE,
    QUESTION_WINDOW,
)
from app.domain.retrieval import RetrievedChunk
from app.main import create_app
from app.models.guest_key import GuestKey
from app.models.message import Message
from app.models.rate_limit_window import RateLimitWindow
from app.models.token_usage_day import TokenUsageDay
from app.prompts.conversations import (
    DIAGNOSTICS_RATE_LIMITED,
    DUPLICATE_FEEDBACK,
    DUPLICATE_MESSAGE,
    FEEDBACK_NOT_ASSISTANT,
    NOT_OWNER,
    RATE_LIMITED,
)
from app.prompts.qa import ABSTENTION, MEDICAL_ADVICE
from app.repositories.conversations import ConversationRepository, MessageRecord
from app.repositories.token_usage import TokenUsageRepository
from app.workflows.qa import QaWorkflow, QuestionClassification
from tests.integration.test_auth import (
    HMAC_KEY,
    PASSWORD,
    FrozenClock,
    _cookie_attributes,
    _delete_email,
    _insert_user,
    _login,
)

pytestmark = pytest.mark.integration

ORIGIN = "http://localhost:5173"
# 12:07 deixa 53 minutos na janela de uma hora: os limites esperam `retry_after_seconds` 3180.
FIXED = datetime(2026, 10, 27, 12, 7, tzinfo=UTC)
CHUNK = UUID("00000000-0000-4000-8000-0000000000c1")
VISITING = "Qual é o horário de visita?"
HEALTH = "Estou com dor no peito"


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch, migrated_database: str) -> TestClient:
    """API real com o adaptador `fake` e o relógio parado. `_use` troca o workflow por teste."""
    _configure(monkeypatch, migrated_database)
    application = create_app()
    application.dependency_overrides[get_clock] = FrozenClock
    return TestClient(application)


def test_guest_asks_and_receives_a_cited_answer(
    api: TestClient,
    migrated_database: str,
) -> None:
    seen: list[list[str]] = []
    created = _create(api)
    conversation_id = UUID(created.json()["id"])
    secret = _guest_secret(created)

    # O gancho roda quando o fluxo começa. Só a pergunta pode estar gravada nesse momento,
    # porque a geração corre fora da transação (seção 6.4).
    async def hook() -> None:
        rows = await _messages(migrated_database, conversation_id)
        seen.append([row.role for row in rows])

    chat = FakeChatProvider(
        structured=_classification("Horário de visita", "public_info", 0.9),
        tokens=["O horário é 11:00 [1]."],
        stream_hook=hook,
    )
    _use(api, chat, [_hit()])
    try:
        response = _ask(api, conversation_id, VISITING)
        body = _events(response.text)
        stored = asyncio.run(_messages(migrated_database, conversation_id))
        loaded = api.get(f"/v1/conversations/{conversation_id}")
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    assert [name for name, _payload in body] == ["meta", "token", "citation", "done"]
    assert body[0][1]["request_id"] == response.headers["x-request-id"]
    assert body[1][1] == {"text": "O horário é 11:00 [1]."}
    assert body[2][1]["chunk_id"] == str(CHUNK)
    assert body[2][1]["document_title"] == "Visitas"
    assert body[2][1]["heading"] == "Horário"
    assert body[3][1] == {"outcome": "answered"}
    assert seen == [["user"]]
    assistant = _assistant(stored)
    assert assistant.content == "O horário é 11:00 [1]."
    assert assistant.outcome == "answered"
    assert str(assistant.id) == body[0][1]["message_id"]
    assert assistant.citations[0].chunk_id == CHUNK
    assert loaded.status_code == 200
    assert loaded.json()["messages"][1]["citations"][0]["document_title"] == "Visitas"


def test_repeated_client_message_id_returns_409_with_the_existing_id(
    api: TestClient,
    migrated_database: str,
) -> None:
    created = _create(api)
    conversation_id = UUID(created.json()["id"])
    secret = _guest_secret(created)
    chat = FakeChatProvider(
        structured=_classification("Horário de visita", "public_info", 0.9),
        tokens=["11:00 [1]."],
    )
    _use(api, chat, [_hit()])
    client_message_id = uuid4()
    try:
        first = _ask(api, conversation_id, VISITING, client_message_id=client_message_id)
        stored = asyncio.run(_messages(migrated_database, conversation_id))
        second = _ask(api, conversation_id, VISITING, client_message_id=client_message_id)
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))
    user = next(row for row in stored if row.role == "user")
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"
    assert second.json()["error"]["message"] == DUPLICATE_MESSAGE
    assert second.json()["error"]["message_id"] == str(user.id)
    assert len(chat.structured_calls) == 1


def test_disconnect_stores_cancelled_and_discards_the_partial(
    monkeypatch: pytest.MonkeyPatch,
    migrated_database: str,
) -> None:
    _configure(monkeypatch, migrated_database)
    asyncio.run(_disconnect(migrated_database))


def test_disconnect_records_the_partial_usage(
    monkeypatch: pytest.MonkeyPatch,
    migrated_database: str,
) -> None:
    """CA-3 da Etapa 12.2: os tokens que o modelo já gerou entram na mensagem e no orçamento.

    A classificação conta (20, 3) e o primeiro token, (0, 5): 20 de entrada e 8 de saída. Os
    (40, 0) do fim do fluxo nunca entram, porque o fluxo é cancelado antes.
    """
    _configure(monkeypatch, migrated_database)
    chat = FakeChatProvider(
        structured=_classification("Horário de visita", "public_info", 0.9),
        structured_usage=(20, 3),
        tokens=["rascunho parcial", "resto"],
        token_usage=(0, 5),
        stream_usage=(40, 0),
        pause_after=1,
    )
    before = asyncio.run(_day_usage(migrated_database))
    stored, tokens = asyncio.run(_cancel_after_first_token(migrated_database, chat))
    after = asyncio.run(_day_usage(migrated_database))
    assert _assistant(stored).outcome == "cancelled"
    assert tokens == (20, 8)
    assert (after[0] - before[0], after[1] - before[1]) == (20, 8)


def test_medical_question_is_stored_as_the_marker(
    api: TestClient,
    migrated_database: str,
) -> None:
    created = _create(api)
    conversation_id = UUID(created.json()["id"])
    secret = _guest_secret(created)
    # Confiança baixa de propósito: `medical_advice` recusa mesmo abaixo de 0,6 (seção 7.1).
    chat = FakeChatProvider(structured=_classification("dor no peito", "medical_advice", 0.4))
    embeddings = _Embeddings()
    _fastapi(api).dependency_overrides[get_qa_workflow] = lambda: QaWorkflow(
        chat,
        embeddings,
        _Search([]),
        minimum_similarity=0.5,
    )
    try:
        response = _ask(api, conversation_id, HEALTH)
        stored = asyncio.run(_messages(migrated_database, conversation_id))
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))
    events = _events(response.text)
    user = next(row for row in stored if row.role == "user")
    assistant = _assistant(stored)
    assert user.content == HEALTH_MESSAGE_MARKER
    assert HEALTH not in user.content
    assert assistant.outcome == "refused"
    assert assistant.content == MEDICAL_ADVICE
    assert events[-1] == ("done", {"outcome": "refused"})
    assert ("token", {"text": MEDICAL_ADVICE}) in events
    assert embeddings.queries == []
    assert chat.stream_calls == []


def test_phone_outside_context_emits_replace(
    api: TestClient,
    migrated_database: str,
) -> None:
    created = _create(api)
    conversation_id = UUID(created.json()["id"])
    secret = _guest_secret(created)
    chat = FakeChatProvider(
        structured=_classification("Telefone da cardiologia", "public_info", 0.9),
        tokens=["Ligue (555) 019-9999 [1]."],
    )
    _use(api, chat, [_hit("A mesa atende no (555) 014-2600.")])
    try:
        response = _ask(api, conversation_id, "Qual é o telefone direto da cardiologia?")
        stored = asyncio.run(_messages(migrated_database, conversation_id))
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))
    events = _events(response.text)
    names = [name for name, _payload in events]
    assert names.index("token") < names.index("replace") < names.index("done")
    replace = next(payload for name, payload in events if name == "replace")
    assert replace == {"text": ABSTENTION, "reason": "grounding_failed"}
    assert "citation" not in names
    assistant = _assistant(stored)
    assert assistant.outcome == "grounding_failed"
    assert assistant.content == ABSTENTION
    assert "019-9999" not in assistant.content


def test_history_sent_to_the_model_comes_from_the_database_without_health_text(
    api: TestClient,
    migrated_database: str,
) -> None:
    created = _create(api)
    conversation_id = UUID(created.json()["id"])
    secret = _guest_secret(created)
    chat = FakeChatProvider(structured=_classification("dor no peito", "medical_advice", 0.9))
    _use(api, chat, [_hit()])
    try:
        _ask(api, conversation_id, HEALTH)
        stored = asyncio.run(_messages(migrated_database, conversation_id))
        # O mesmo falso responde a segunda pergunta como informação pública. A reescrita dela
        # recebe o histórico lido do banco, com o marcador no lugar do texto (seção 11.4).
        chat.script(
            structured=_classification("Horário de visita", "public_info", 0.9),
            tokens=["11:00 [1]."],
        )
        _ask(api, conversation_id, "E no fim de semana?")
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))
    user_text = [row.content for row in stored if row.role == "user"]
    assert user_text == [HEALTH_MESSAGE_MARKER]
    follow_up = "\n".join(message.content for message in chat.structured_calls[-1][0])
    assert HEALTH_MESSAGE_MARKER in follow_up
    assert HEALTH not in follow_up


def test_feedback_reaches_the_sink_for_the_assistant_run(
    api: TestClient,
    migrated_database: str,
) -> None:
    seen: list[tuple[UUID, str, float]] = []

    class Sink:
        """Falso do `FeedbackSink`: guarda cada nota em vez de mandar ao LangSmith."""

        async def record(self, run_id: UUID, key: str, score: float) -> None:
            seen.append((run_id, key, score))

    sink = Sink()
    _fastapi(api).dependency_overrides[get_feedback_sink] = lambda: sink
    created = _create(api)
    conversation_id = UUID(created.json()["id"])
    secret = _guest_secret(created)
    _use(
        api,
        FakeChatProvider(
            structured=_classification("Horário de visita", "public_info", 0.9),
            tokens=["11:00 [1]."],
        ),
        [_hit()],
    )
    try:
        _ask(api, conversation_id, VISITING)
        stored = asyncio.run(_messages(migrated_database, conversation_id))
        assistant = _assistant(stored)
        response = api.post(
            f"/v1/messages/{assistant.id}/feedback",
            headers=_headers(),
            json={"rating": -1},
        )
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))
    assert response.status_code == 201
    assert seen == [(assistant.id, "user_helpful", 0.0)]


def test_second_feedback_is_rejected(api: TestClient, migrated_database: str) -> None:
    created = _create(api)
    conversation_id = UUID(created.json()["id"])
    secret = _guest_secret(created)
    _use(
        api,
        FakeChatProvider(
            structured=_classification("Horário de visita", "public_info", 0.9),
            tokens=["11:00 [1]."],
        ),
        [_hit()],
    )
    try:
        _ask(api, conversation_id, VISITING)
        stored = asyncio.run(_messages(migrated_database, conversation_id))
        assistant = _assistant(stored)
        user = next(row for row in stored if row.role == "user")
        first = api.post(
            f"/v1/messages/{assistant.id}/feedback",
            headers=_headers(),
            json={"rating": 1},
        )
        second = api.post(
            f"/v1/messages/{assistant.id}/feedback",
            headers=_headers(),
            json={"rating": -1},
        )
        on_user = api.post(
            f"/v1/messages/{user.id}/feedback",
            headers=_headers(),
            json={"rating": 1},
        )
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))
    assert first.status_code == 201
    assert first.json() == {"message_id": str(assistant.id), "rating": 1}
    assert second.status_code == 409
    assert second.json()["error"]["message"] == DUPLICATE_FEEDBACK
    assert on_user.status_code == 422
    assert on_user.json()["error"]["message"] == FEEDBACK_NOT_ASSISTANT


def test_only_the_owner_reads_the_conversation(
    api: TestClient,
    migrated_database: str,
) -> None:
    # Cada `TestClient` tem o próprio pote de cookies: `owner` e `other` são dois convidados.
    owner = TestClient(api.app)
    other = TestClient(api.app)
    created = _create(owner)
    other_created = _create(other)
    conversation_id = created.json()["id"]
    secret = _guest_secret(created)
    other_secret = _guest_secret(other_created)
    email = f"owner-{uuid4().hex}@example.com"
    try:
        asyncio.run(_insert_user(migrated_database, email=email, role="member"))
        logged_in = _login(api, email, PASSWORD)
        denied = other.get(f"/v1/conversations/{conversation_id}")
        missing = TestClient(api.app).get(f"/v1/conversations/{conversation_id}")
        allowed = owner.get(f"/v1/conversations/{conversation_id}")
        member = api.get(
            f"/v1/conversations/{conversation_id}",
            headers={"cookie": f"atrium_session={logged_in.cookies.get('atrium_session')}"},
        )
        guest_list = owner.get("/v1/conversations")
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))
        asyncio.run(_delete_guest(migrated_database, other_secret))
        asyncio.run(_delete_email(migrated_database, email))
    assert denied.status_code == 403
    assert denied.json()["error"]["message"] == NOT_OWNER
    assert missing.status_code == 401
    assert allowed.status_code == 200
    assert member.status_code == 403
    assert member.json()["error"]["message"] == NOT_OWNER
    assert guest_list.status_code == 401


def test_guest_cookie_is_host_only_and_reused(api: TestClient, migrated_database: str) -> None:
    first = _create(api)
    secret = _guest_secret(first)
    try:
        second = _create(api)
        guests = asyncio.run(_guest_count(migrated_database, secret))
        stored_hash = asyncio.run(_stored_hash(migrated_database, secret))
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))
    assert first.status_code == 201
    assert first.headers["cache-control"] == "no-store"
    attributes = _cookie_attributes(first)
    assert "httponly" in attributes
    assert attributes["samesite"] == "lax"
    assert attributes["max-age"] == "2592000"
    assert "domain" not in attributes
    assert "secure" not in attributes
    assert second.status_code == 201
    assert "set-cookie" not in second.headers
    assert guests == 1
    assert stored_hash == hash_session_secret(secret)
    assert stored_hash != secret


def test_guest_question_rate_limit_returns_429(api: TestClient, migrated_database: str) -> None:
    created = _create(api)
    conversation_id = UUID(created.json()["id"])
    secret = _guest_secret(created)
    ip = f"guest-{uuid4().hex}"
    chat = FakeChatProvider(structured=_classification("visita", "public_info", 0.9))
    _use(api, chat, [_hit()])
    try:
        guest_id = asyncio.run(_guest_id(migrated_database, secret))
        # A janela da chave de convidado já tem as 30 perguntas da hora (seção 10.4).
        asyncio.run(
            _seed_window(
                migrated_database,
                key=bucket_key(
                    purpose=QUESTION_GUEST_KEY_PURPOSE,
                    subject=str(guest_id),
                    day=FIXED.date(),
                    key=HMAC_KEY,
                ),
                start=fixed_window_start(FIXED, QUESTION_WINDOW),
                count=30,
            )
        )
        response = _ask(api, conversation_id, VISITING, ip=ip)
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))
    assert response.status_code == 429
    assert response.json()["error"]["message"] == RATE_LIMITED
    assert response.json()["error"]["retry_after_seconds"] == 3180
    assert chat.structured_calls == []


def test_guest_ip_and_member_question_buckets(
    api: TestClient,
    migrated_database: str,
) -> None:
    """O membro não recebe cookie de convidado e para no balde de 120 perguntas por hora."""
    email = f"member-{uuid4().hex}@example.com"
    ip = f"member-{uuid4().hex}"
    try:
        asyncio.run(_insert_user(migrated_database, email=email, role="member"))
        logged_in = _login(api, email, PASSWORD)
        session = logged_in.cookies.get("atrium_session")
        assert isinstance(session, str)
        created = api.post(
            "/v1/conversations",
            headers=_headers(ip=ip, cookie=f"atrium_session={session}"),
        )
        assert "atrium_guest" not in created.headers.get("set-cookie", "")
        user_id = logged_in.json()["id"]
        asyncio.run(
            _seed_window(
                migrated_database,
                key=bucket_key(
                    purpose=QUESTION_MEMBER_PURPOSE,
                    subject=user_id,
                    day=FIXED.date(),
                    key=HMAC_KEY,
                ),
                start=fixed_window_start(FIXED, QUESTION_WINDOW),
                count=120,
            )
        )
        chat = FakeChatProvider(structured=_classification("visita", "public_info", 0.9))
        _use(api, chat, [_hit()])
        limited = _ask(
            api,
            UUID(created.json()["id"]),
            VISITING,
            ip=ip,
            cookie=f"atrium_session={session}",
        )
    finally:
        asyncio.run(_delete_email(migrated_database, email))
    assert created.status_code == 201
    assert limited.status_code == 429
    assert limited.json()["error"]["retry_after_seconds"] == 3180
    assert chat.structured_calls == []


def test_diagnostics_stream_emits_three_ticks_one_second_apart(api: TestClient) -> None:
    started = time.perf_counter()
    response = api.get("/v1/diagnostics/stream", headers={"X-Forwarded-For": f"diag-{uuid4().hex}"})
    elapsed = time.perf_counter() - started
    events = _events(response.text)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert events == [("tick", {"index": 1}), ("tick", {"index": 2}), ("tick", {"index": 3})]
    # Três ticks, um por segundo, dão dois intervalos de 1 s; 1,8 deixa folga ao relógio.
    assert elapsed >= 1.8


def test_diagnostics_rate_limit_returns_429(api: TestClient, migrated_database: str) -> None:
    ip = f"diag-limit-{uuid4().hex}"
    start = fixed_window_start(FIXED, DIAGNOSTICS_WINDOW)
    key = bucket_key(purpose=DIAGNOSTICS_IP_PURPOSE, subject=ip, day=FIXED.date(), key=HMAC_KEY)
    asyncio.run(_seed_window(migrated_database, key=key, start=start, count=60))
    started = time.perf_counter()
    response = api.get("/v1/diagnostics/stream", headers={"X-Forwarded-For": ip})
    elapsed = time.perf_counter() - started
    assert response.status_code == 429
    assert response.json()["error"]["message"] == DIAGNOSTICS_RATE_LIMITED
    assert response.json()["error"]["retry_after_seconds"] == 3180
    # O 429 sai antes de o fluxo começar, sem esperar nenhum tick.
    assert elapsed < 1


def test_budget_exhaustion_does_not_call_the_model(
    monkeypatch: pytest.MonkeyPatch,
    migrated_database: str,
) -> None:
    _configure(monkeypatch, migrated_database)
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "1")
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_clock] = FrozenClock
    chat = FakeChatProvider(structured=_classification("visita", "public_info", 0.9))
    application.dependency_overrides[get_qa_workflow] = lambda: _workflow(chat, [_hit()])
    client = TestClient(application)
    # O uso do dia iguala o teto de 1, e igualar já degrada (seção 7.1).
    asyncio.run(_seed_usage(migrated_database))
    created = _create(client)
    secret = _guest_secret(created)
    try:
        response = _ask(client, UUID(created.json()["id"]), VISITING)
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))
        get_settings.cache_clear()
    assert _events(response.text)[-1] == ("done", {"outcome": "degraded"})
    assert chat.structured_calls == []


def test_member_lists_only_their_conversations(
    api: TestClient,
    migrated_database: str,
) -> None:
    email = f"list-{uuid4().hex}@example.com"
    other = f"other-{uuid4().hex}@example.com"
    guest = _create(api)
    secret = _guest_secret(guest)
    try:
        asyncio.run(_insert_user(migrated_database, email=email, role="member"))
        asyncio.run(_insert_user(migrated_database, email=other, role="member"))
        session = _login(api, email, PASSWORD).cookies.get("atrium_session")
        other_session = _login(api, other, PASSWORD).cookies.get("atrium_session")
        assert isinstance(session, str)
        assert isinstance(other_session, str)
        cookie = {"cookie": f"atrium_session={session}"}
        first = api.post("/v1/conversations", headers={**_headers(), **cookie})
        second = api.post("/v1/conversations", headers={**_headers(), **cookie})
        listed = api.get("/v1/conversations", headers=cookie)
        foreign = api.get(
            "/v1/conversations",
            headers={"cookie": f"atrium_session={other_session}"},
        )
    finally:
        asyncio.run(_delete_guest(migrated_database, secret))
        asyncio.run(_delete_email(migrated_database, email))
        asyncio.run(_delete_email(migrated_database, other))
    ids = [item["id"] for item in listed.json()["conversations"]]
    assert ids == [second.json()["id"], first.json()["id"]]
    assert guest.json()["id"] not in ids
    assert foreign.json()["conversations"] == []


def _configure(monkeypatch: pytest.MonkeyPatch, database_url: str) -> None:
    """Variáveis da API dos testes: banco local, adaptador `fake` e teto de tokens desligado."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", HMAC_KEY)
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_AI_ADAPTER", "fake")
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "0")
    get_settings.cache_clear()


def _use(api: TestClient, chat: FakeChatProvider, hits: list[RetrievedChunk]) -> None:
    """Troca o `get_qa_workflow` do app por um `QaWorkflow` com o chat e os chunks do teste."""
    workflow = _workflow(chat, hits)
    _fastapi(api).dependency_overrides[get_qa_workflow] = lambda: workflow


def _fastapi(client: TestClient) -> FastAPI:
    """O `FastAPI` por trás do `TestClient`, para mexer nos `dependency_overrides`."""
    app = client.app
    if not isinstance(app, FastAPI):
        raise AssertionError(type(app))
    return app


def _workflow(chat: FakeChatProvider, hits: Sequence[RetrievedChunk]) -> QaWorkflow:
    """`QaWorkflow` com o chat do teste, `_Embeddings`, `_Search` com `hits` e piso 0,5."""
    return QaWorkflow(chat, _Embeddings(), _Search(list(hits)), minimum_similarity=0.5)


def _create(client: TestClient) -> Any:
    """`POST /v1/conversations`. Sem sessão, a API cria a chave e o cookie de convidado."""
    return client.post("/v1/conversations", headers=_headers())


def _ask(
    client: TestClient,
    conversation_id: UUID,
    text: str,
    *,
    client_message_id: UUID | None = None,
    ip: str | None = None,
    cookie: str | None = None,
) -> Any:
    """Envia uma pergunta e devolve a resposta com o fluxo SSE inteiro no corpo."""
    return client.post(
        f"/v1/conversations/{conversation_id}/messages",
        headers=_headers(ip=ip, cookie=cookie),
        json={"text": text, "client_message_id": str(client_message_id or uuid4())},
    )


def _headers(ip: str | None = None, cookie: str | None = None) -> dict[str, str]:
    """`Origin` certo e um IP único, mais o `cookie` quando informado."""
    headers = {"Origin": ORIGIN, "X-Forwarded-For": ip or f"test-{uuid4().hex}"}
    if cookie is not None:
        headers["cookie"] = cookie
    return headers


def _guest_secret(response: Any) -> str:
    """Segredo do cookie `atrium_guest` da resposta. Falha sem ele."""
    secret = response.cookies.get("atrium_guest")
    if not isinstance(secret, str) or not secret:
        raise AssertionError(response.headers)
    return secret


def _events(body: str) -> list[tuple[str, dict[str, Any]]]:
    """Lê o corpo SSE como pares de evento e carga JSON, na ordem."""
    found: list[tuple[str, dict[str, Any]]] = []
    name = ""
    for line in body.splitlines():
        if line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: ") and name:
            payload = json.loads(line.removeprefix("data: "))
            if isinstance(payload, dict):
                found.append((name, payload))
            name = ""
    return found


def _assistant(rows: list[MessageRecord]) -> MessageRecord:
    """A mensagem do assistente entre as gravadas."""
    return next(row for row in rows if row.role == "assistant")


def _classification(
    question: str,
    intent: Literal["public_info", "medical_advice", "other"],
    confidence: float,
) -> QuestionClassification:
    """Saída estruturada da reescrita: pergunta autônoma, intenção e confiança (seção 7.1)."""
    return QuestionClassification(
        standalone_question=question,
        intent=intent,
        confidence=confidence,
    )


def _hit(content: str = "11:00 às 20:00.") -> RetrievedChunk:
    """Chunk recuperado do documento de visitas, com similaridade 0,9 e o id fixo `CHUNK`."""
    return RetrievedChunk(
        chunk_id=CHUNK,
        document_slug="02-visiting",
        document_title="Visitas",
        heading="Horário",
        content=content,
        similarity=0.9,
    )


class _Embeddings:
    """Embedding falso de 3 dimensões: guarda as perguntas e falha se embedar documento."""

    model_name = "fake-embedding"
    dimensions = 3

    def __init__(self) -> None:
        self.queries: list[str] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError(texts)

    async def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1, 0.2, 0.3]


class _Search:
    """Busca falsa: devolve os chunks escritos no teste, sem tocar no banco."""

    def __init__(self, hits: list[RetrievedChunk]) -> None:
        self._hits = hits

    async def search_by_vector(
        self,
        question: str,
        embedding: list[float],
    ) -> list[RetrievedChunk]:
        del question, embedding
        return self._hits


async def _disconnect(database_url: str) -> None:
    """Desconecta depois do primeiro token e confere `cancelled` sem o rascunho parcial."""
    chat = FakeChatProvider(
        structured=_classification("Horário de visita", "public_info", 0.9),
        tokens=["rascunho parcial", "resto"],
        pause_after=1,
    )
    stored, _tokens = await _cancel_after_first_token(database_url, chat)
    assistant = _assistant(stored)
    user = next(row for row in stored if row.role == "user")
    assert assistant.outcome == "cancelled"
    assert assistant.content == ""
    assert "rascunho parcial" not in assistant.content
    assert user.content == VISITING


async def _cancel_after_first_token(
    database_url: str,
    chat: FakeChatProvider,
) -> tuple[list[MessageRecord], tuple[int, int]]:
    """Desconecta depois do primeiro token. Devolve as mensagens e os tokens da resposta.

    O `chat` precisa de `pause_after=1`: o falso segura o fluxo depois do primeiro token por até
    3 s. Sem o cancelamento, ele levantaria `ProviderUnavailable`, e o teste não veria
    `cancelled`. Monta um app próprio e apaga a chave de convidado no fim.
    """
    application = create_app()
    application.dependency_overrides[get_clock] = FrozenClock
    application.dependency_overrides[get_qa_workflow] = lambda: _workflow(chat, [_hit()])
    transport = ASGITransport(app=application)
    secret = ""
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post("/v1/conversations", headers=_headers())
            assert created.status_code == 201
            secret = created.cookies["atrium_guest"]
            conversation_id = created.json()["id"]
        await _close_after_first_token(application, conversation_id, secret)
        stored = await _messages(database_url, UUID(conversation_id))
        tokens = await _message_tokens(database_url, _assistant(stored).id)
    finally:
        if secret:
            await _delete_guest(database_url, secret)
    return stored, tokens


async def _message_tokens(database_url: str, message_id: UUID) -> tuple[int, int]:
    """Tokens de entrada e de saída gravados na mensagem."""
    async with open_session(database_url) as session, UnitOfWork(session):
        row = (
            await session.execute(
                select(Message.input_tokens, Message.output_tokens).where(Message.id == message_id)
            )
        ).one()
    return (row.input_tokens, row.output_tokens)


async def _day_usage(database_url: str) -> tuple[int, int]:
    """Tokens do dia de `FIXED` em `token_usage_days`."""
    async with open_session(database_url) as session, UnitOfWork(session):
        return await TokenUsageRepository(session).totals(FIXED.date())
    # Inalcançável: o `__aexit__` do `UnitOfWork` devolve `bool`, então o mypy supõe que o bloco
    # pode engolir a exceção e exige um fim depois dele.
    raise AssertionError("token usage")


async def _close_after_first_token(app: object, conversation_id: str, secret: str) -> None:
    """Envia `http.disconnect` depois do primeiro token. O httpx espera o app terminar.

    Por isso o teste chama o app ASGI direto: `receive` entrega o corpo e depois espera o
    primeiro `event: token` chegar em `send` para devolver `http.disconnect`.
    """
    body = json.dumps(
        {"text": VISITING, "client_message_id": str(uuid4())},
    ).encode()
    closed = asyncio.Event()
    received = bytearray()
    request_sent = False

    async def receive() -> dict[str, object]:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await closed.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, object]) -> None:
        if message.get("type") != "http.response.body":
            return
        chunk = message.get("body", b"")
        if isinstance(chunk, bytes):
            received.extend(chunk)
        if b"event: token" in received:
            closed.set()

    path = f"/v1/conversations/{conversation_id}/messages"
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.5"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [
            (b"origin", ORIGIN.encode()),
            (b"content-type", b"application/json"),
            (b"cookie", f"atrium_guest={secret}".encode()),
            (b"x-forwarded-for", b"127.0.0.1"),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
        "root_path": "",
    }
    await app(scope, receive, send)  # type: ignore[operator]


async def _messages(database_url: str, conversation_id: UUID) -> list[MessageRecord]:
    """Mensagens da conversa, lidas pelo repositório."""
    found: list[MessageRecord] = []
    async with open_session(database_url) as session, UnitOfWork(session):
        found = await ConversationRepository(session).list_messages(conversation_id)
    return found


async def _delete_guest(database_url: str, secret: str) -> None:
    """Apaga a chave de convidado. Conversas, mensagens e feedback dela caem em cascata."""
    async with open_session(database_url) as session, UnitOfWork(session):
        await session.execute(
            delete(GuestKey).where(GuestKey.token_hash == hash_session_secret(secret))
        )


async def _guest_count(database_url: str, secret: str) -> int:
    """Quantas chaves de convidado têm o hash deste segredo."""
    async with open_session(database_url) as session:
        rows = await session.scalars(
            select(GuestKey.id).where(GuestKey.token_hash == hash_session_secret(secret))
        )
    return len(list(rows))


async def _guest_id(database_url: str, secret: str) -> UUID:
    """Id da chave de convidado deste segredo."""
    async with open_session(database_url) as session:
        guest_id = await session.scalar(
            select(GuestKey.id).where(GuestKey.token_hash == hash_session_secret(secret))
        )
    if not isinstance(guest_id, UUID):
        raise AssertionError(guest_id)
    return guest_id


async def _stored_hash(database_url: str, secret: str) -> str:
    """`token_hash` gravado para este segredo de convidado."""
    async with open_session(database_url) as session:
        stored = await session.scalar(
            select(GuestKey.token_hash).where(GuestKey.token_hash == hash_session_secret(secret))
        )
    if not isinstance(stored, str):
        raise AssertionError(stored)
    return stored


async def _seed_window(database_url: str, *, key: str, start: datetime, count: int) -> None:
    """Grava uma janela de limite já com `count` pedidos, para o próximo passar do limite."""
    async with open_session(database_url) as session, UnitOfWork(session):
        session.add(RateLimitWindow(bucket_key=key, window_start=start, count=count))


async def _seed_usage(database_url: str) -> None:
    """Põe 1 token de entrada no dia de `FIXED`, o bastante para o teto de 1 estourar."""
    async with open_session(database_url) as session, UnitOfWork(session):
        await session.execute(delete(TokenUsageDay).where(TokenUsageDay.day == FIXED.date()))
        session.add(TokenUsageDay(day=FIXED.date(), input_tokens=1, output_tokens=0))
