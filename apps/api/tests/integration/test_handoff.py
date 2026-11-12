"""Atendimento humano com o PostgreSQL local: papéis, pedido, fila, mensagens e varredura.

Etapas 17.2, 17.4 e 17.5. FR-19, FR-21, FR-22, FR-24 a FR-26, NFR-18, NFR-20 e seções 29.3 a
29.10 do SDD. O `TestClient` chama a API real com o adaptador `fake`, `HANDOFF_ENABLED=true`, um
relógio que o teste avança e o `InMemoryBroker`. Cada cliente tem o próprio pote de cookies: o
visitante é um convidado e a equipe entra pelo login. As corridas (dois atendentes ao mesmo
tempo, duas varreduras) chamam os serviços direto, num loop só. Os fluxos SSE ficam em
`test_realtime.py`. Precisa de PostgreSQL com pgvector local (`migrated_database`).
"""

import asyncio
from collections.abc import Coroutine, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app.adapters.fake_chat import FakeChatProvider
from app.adapters.password_hasher import get_password_hasher
from app.adapters.realtime import InMemoryBroker
from app.core.container import get_clock, get_settings
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import hash_session_secret
from app.domain.errors import HandoffTaken
from app.domain.handoff import StaffMember
from app.domain.legal import ATTENDANT_TERMS_VERSION
from app.main import create_app
from app.models.audit_event import AuditEvent
from app.models.guest_key import GuestKey
from app.models.message import Message
from app.models.user import User
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.handoffs import HandoffRepository
from app.repositories.users import UserRepository
from app.services.attendance import AttendanceService
from app.services.attendant_roles import AttendantRoleService
from app.services.handoff_sweep import HandoffSweeper
from tests.integration.test_auth import HMAC_KEY, PASSWORD
from tests.integration.test_conversations import _use

pytestmark = pytest.mark.integration

ORIGIN = "http://localhost:5173"
NOW = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)
PSEUDONYM_KEY = "test-pseudonym-key"


class MovingClock:
    """Relógio que o teste avança, para vencer a fila, a presença e a inatividade."""

    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def advance(self, **delta: float) -> None:
        self.current += timedelta(**delta)


@pytest.fixture
def clock() -> MovingClock:
    return MovingClock(NOW)


@pytest.fixture
def broker() -> InMemoryBroker:
    return InMemoryBroker()


@pytest.fixture
def api(
    monkeypatch: pytest.MonkeyPatch,
    migrated_database: str,
    clock: MovingClock,
    broker: InMemoryBroker,
) -> Iterator[TestClient]:
    """API real com o atendimento ligado, o relógio do teste e o broker em memória."""
    yield api_client(monkeypatch, migrated_database, clock, broker)
    get_settings.cache_clear()


def api_client(
    monkeypatch: pytest.MonkeyPatch,
    database_url: str,
    clock: MovingClock,
    broker: InMemoryBroker,
) -> TestClient:
    """Monta o `TestClient` do atendimento. `test_realtime.py` usa o mesmo."""
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", HMAC_KEY)
    monkeypatch.setenv("PSEUDONYM_KEY", PSEUDONYM_KEY)
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_AI_ADAPTER", "fake")
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", "0")
    monkeypatch.setenv("HANDOFF_ENABLED", "true")
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_clock] = lambda: clock
    application.state.realtime_broker = broker
    return TestClient(application)


@pytest.fixture
def people(migrated_database: str) -> Iterator["People"]:
    """Cria contas e convidados do teste e apaga tudo no fim, na ordem das chaves."""
    created = People(migrated_database)
    yield created
    asyncio.run(created.cleanup())


class People:
    """As contas e as chaves de convidado criadas por um teste."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.emails: list[str] = []
        self.guest_secrets: list[str] = []

    def account(self, role: str) -> str:
        """Uma conta nova com o papel e a senha `PASSWORD`. Devolve o e-mail."""
        email = f"{role}-{uuid4().hex}@example.com"
        self.emails.append(email)
        asyncio.run(_insert(self.database_url, email, role))
        return email

    async def cleanup(self) -> None:
        """Apaga convidados e contas, com as conversas, sessões e auditoria delas."""
        async with open_session(self.database_url) as session, UnitOfWork(session):
            for secret in self.guest_secrets:
                await session.execute(
                    delete(GuestKey).where(GuestKey.token_hash == hash_session_secret(secret))
                )
            for email in self.emails:
                user = await UserRepository(session).get_by_email(email)
                if user is None:
                    continue
                await session.execute(
                    text(
                        "DELETE FROM conversations WHERE user_id = :id OR id IN "
                        "(SELECT conversation_id FROM handoffs WHERE attendant_id = :id)"
                    ),
                    {"id": user.id},
                )
                await AuthSessionRepository(session).delete_for_user(user.id)
                await session.execute(
                    delete(AuditEvent).where(
                        (AuditEvent.actor_user_id == user.id) | (AuditEvent.target_id == user.id)
                    )
                )
                await session.execute(delete(User).where(User.id == user.id))


def test_migration_0010_downgrades_and_upgrades(migrated_database: str) -> None:
    # Etapa 17.2, CA-1: a migração volta para a `0009` e sobe de novo até o topo.
    from alembic import command
    from alembic.config import Config

    from tests.integration.conftest import API_ROOT

    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", migrated_database.replace("%", "%%"))
    command.downgrade(config, "0009_message_request_id")
    assert _run(_revision(migrated_database)) == "0009_message_request_id"
    command.upgrade(config, "head")
    assert _run(_revision(migrated_database)) == "0010_handoffs"


def test_script_promotes_only_members_and_audits(people: People, migrated_database: str) -> None:
    # Etapa 17.2, CA-2: só `member` vira `attendant`, admin é recusado, e há auditoria.
    admin = people.account("admin")
    member = people.account("member")
    other_admin = people.account("admin")
    service = AttendantRoleService(database_url=migrated_database, clock=MovingClock(NOW))
    granted = asyncio.run(service.grant(member, by=admin))
    assert _run(_role(migrated_database, member)) == "attendant"
    with pytest.raises(Exception, match="admin"):
        asyncio.run(service.grant(other_admin, by=admin))
    revoked = asyncio.run(service.revoke(member, by=admin))
    assert _run(_role(migrated_database, member)) == "member"
    actions = _run(_actions(migrated_database, granted.user_id))
    assert actions == ["attendant.grant", "attendant.revoke"]
    assert revoked.user_id == granted.user_id


def test_attendant_and_member_roles_are_separated(api: TestClient, people: People) -> None:
    # Etapa 17.2, CA-3: `attendant` recebe 403 no admin e `member` recebe 403 no console.
    attendant = _login(api, people.account("attendant"))
    member = _login(api, people.account("member"))
    assert attendant.get("/v1/admin/documents").status_code == 403
    assert member.get("/v1/attendance/queue").status_code == 403
    assert TestClient(api.app).get("/v1/attendance/queue").status_code == 401
    assert attendant.get("/v1/attendance/queue").status_code == 200


def test_staff_session_lasts_12_hours(api: TestClient, people: People) -> None:
    # Etapa 17.2, CA-4 (decisão D-8): `attendant` e `admin` ganham 12 horas no cookie.
    for role in ("attendant", "admin"):
        client = TestClient(api.app)
        response = _post(
            client, "/v1/auth/login", {"email": people.account(role), "password": PASSWORD}
        )
        assert response.status_code == 200
        header = response.headers.get_list("set-cookie")[0].lower()
        assert "max-age=43200" in header
    member = TestClient(api.app)
    response = _post(
        member, "/v1/auth/login", {"email": people.account("member"), "password": PASSWORD}
    )
    assert "max-age=1209600" in response.headers.get_list("set-cookie")[0].lower()


def test_me_reports_the_acknowledgement(api: TestClient, people: People) -> None:
    # Etapa 17.2, CA-5: sem o aceite vigente, `acknowledged` é falso.
    attendant = _login(api, people.account("attendant"))
    before = attendant.get("/v1/attendance/me").json()
    assert before == {
        "presence": "away",
        "acknowledged": False,
        "terms_version": ATTENDANT_TERMS_VERSION,
    }
    wrong = _post(attendant, "/v1/attendance/acknowledgement", {"version": "old"})
    assert wrong.status_code == 422
    after = _post(attendant, "/v1/attendance/acknowledgement", {"version": ATTENDANT_TERMS_VERSION})
    assert after.json()["acknowledged"] is True


def test_request_follows_the_offer_rule(api: TestClient, people: People) -> None:
    # Etapa 17.4, CA-1 (FR-19): `refused` não oferece, e a resposta precisa ser a última.
    _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people, outcome="refused")
    refused = _request(visitor, conversation_id, answer_id)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "handoff_not_offered"
    visitor, conversation_id, answer_id = _guest_conversation(api, people, outcome="abstained")
    wrong_message = _request(visitor, conversation_id, uuid4())
    assert wrong_message.json()["error"]["code"] == "handoff_not_offered"
    created = _request(visitor, conversation_id, answer_id)
    assert created.status_code == 201
    assert created.json()["status"] == "queued"
    assert created.json()["queue_position"] >= 1


def test_request_needs_someone_present(api: TestClient, people: People) -> None:
    # Seção 29.4: sem ninguém presente, 503 `handoff_unavailable` com `closed`.
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    assert api.get("/v1/handoff/availability").json() == {"status": "closed"}
    response = _request(visitor, conversation_id, answer_id)
    assert response.status_code == 503
    assert response.json()["error"]["availability"] == "closed"


def test_ask_during_handoff_is_409_and_the_model_is_not_called(
    api: TestClient, people: People
) -> None:
    # Etapa 17.4, CA-2 (FR-21): a pergunta à IA não grava nada nem chama o modelo.
    _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    assert _request(visitor, conversation_id, answer_id).status_code == 201
    chat = FakeChatProvider()
    _use(api, chat, [])
    response = _post(
        visitor,
        f"/v1/conversations/{conversation_id}/messages",
        {"text": "E o estacionamento?", "client_message_id": str(uuid4())},
    )
    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "handoff_active"
    assert body["conversation_id"] == str(conversation_id)
    assert chat.structured_calls == [] and chat.stream_calls == []


def test_visitor_message_is_stored_with_markers(
    api: TestClient, people: People, migrated_database: str
) -> None:
    # Etapa 17.4, CA-3 (FR-25): a mensagem gravada já tem os marcadores.
    _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    assert _request(visitor, conversation_id, answer_id).status_code == 201
    response = _post(
        visitor,
        f"/v1/conversations/{conversation_id}/handoff/messages",
        {
            "text": (
                "Meu CPF é 529.982.247-25 e o e-mail ana@example.com. Liguei no (555) 014-2600."
            ),
            "client_message_id": str(uuid4()),
        },
    )
    assert response.status_code == 201
    expected = "Meu CPF é [CPF removido] e o e-mail [e-mail removido]. Liguei no (555) 014-2600."
    assert response.json()["content"] == expected
    assert response.json()["seq"] == 1
    stored = _run(_handoff_contents(migrated_database, conversation_id))
    assert stored == [expected]


def test_second_request_returns_the_same_and_another_conversation_conflicts(
    api: TestClient, people: People
) -> None:
    # Etapa 17.4, CA-4: o mesmo atendimento com 200, e outra conversa recebe 409.
    _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    first = _request(visitor, conversation_id, answer_id)
    second = _request(visitor, conversation_id, answer_id)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    other_id, other_answer = _run(
        _conversation_with_answer(visitor, people.database_url, "abstained")
    )
    other = _request(visitor, other_id, other_answer)
    assert other.status_code == 409
    assert other.json()["error"]["handoff_id"] == first.json()["id"]


def test_visitor_leaves_the_queue_and_ends_the_handoff(api: TestClient, people: People) -> None:
    # Etapa 17.4, CA-5 (FR-24): na fila, `visitor_cancelled`; em atendimento, `visitor_ended`.
    attendant = _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    _request(visitor, conversation_id, answer_id)
    left = _post(visitor, f"/v1/conversations/{conversation_id}/handoff/end", None)
    assert left.json()["close_reason"] == "visitor_cancelled"
    again = _post(visitor, f"/v1/conversations/{conversation_id}/handoff/end", None)
    assert again.json() == left.json()
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    handoff_id = _request(visitor, conversation_id, answer_id).json()["id"]
    assert _post(attendant, f"/v1/attendance/handoffs/{handoff_id}/take", None).status_code == 200
    ended = _post(visitor, f"/v1/conversations/{conversation_id}/handoff/end", None)
    assert ended.json()["close_reason"] == "visitor_ended"
    late = _post(
        visitor,
        f"/v1/conversations/{conversation_id}/handoff/messages",
        {"text": "Oi?", "client_message_id": str(uuid4())},
    )
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "handoff_closed"


def test_request_limit_answers_429(api: TestClient, people: People) -> None:
    # Etapa 17.4, CA-6 (NFR-20): 3 pedidos por hora por visitante.
    _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    for _ in range(3):
        assert _request(visitor, conversation_id, answer_id).status_code == 201
        _post(visitor, f"/v1/conversations/{conversation_id}/handoff/end", None)
    limited = _request(visitor, conversation_id, answer_id)
    assert limited.status_code == 429
    assert limited.json()["error"]["retry_after_seconds"] > 0


def test_two_attendants_take_at_the_same_time(
    api: TestClient, people: People, migrated_database: str, broker: InMemoryBroker
) -> None:
    # Etapa 17.5, CA-1 (FR-22): um assume, o outro recebe 409 `handoff_taken`.
    _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    handoff_id = UUID(_request(visitor, conversation_id, answer_id).json()["id"])
    first = _run(_staff_member(migrated_database, people.account("attendant")))
    second = _run(_staff_member(migrated_database, people.account("attendant")))
    service = _attendance(migrated_database, broker)
    _run(_acknowledge(migrated_database, first, second))

    async def race() -> list[object]:
        return list(
            await asyncio.gather(
                service.take(first, handoff_id),
                service.take(second, handoff_id),
                return_exceptions=True,
            )
        )

    results = asyncio.run(race())
    assert sum(isinstance(item, HandoffTaken) for item in results) == 1
    assert sum(not isinstance(item, BaseException) for item in results) == 1


def test_queue_has_no_content_and_the_other_attendant_gets_404(
    api: TestClient, people: People
) -> None:
    # Etapa 17.5, CA-2 e CA-3 (FR-22, NFR-18, seção 29.9.4).
    first = _staff_ready(api, people)
    second = _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    handoff_id = _request(visitor, conversation_id, answer_id).json()["id"]
    queue = first.get("/v1/attendance/queue").json()
    item = next(row for row in queue["queued"] if row["handoff_id"] == handoff_id)
    assert set(item) == {
        "handoff_id",
        "label",
        "status",
        "trigger",
        "requested_at",
        "queued_at",
        "assigned_at",
        "closed_at",
        "close_reason",
        "returned",
        "visitor_present",
        "seq",
    }
    assert item["label"].startswith("Visitante ") and len(item["label"]) == len("Visitante ") + 8
    taken = _post(first, f"/v1/attendance/handoffs/{handoff_id}/take", None)
    assert taken.status_code == 200
    assert taken.json()["conversation"][-1]["role"] == "assistant"
    message_id = _post(
        visitor,
        f"/v1/conversations/{conversation_id}/handoff/messages",
        {"text": "Olá", "client_message_id": str(uuid4())},
    ).json()["id"]
    base = f"/v1/attendance/handoffs/{handoff_id}"
    assert second.get(base).status_code == 404
    assert (
        _post(
            second, f"{base}/messages", {"text": "x", "client_message_id": str(uuid4())}
        ).status_code
        == 404
    )
    assert _post(second, f"{base}/release", None).status_code == 404
    assert _post(second, f"{base}/close", {"reason": "resolved"}).status_code == 404
    assert (
        _post(second, f"{base}/messages/{message_id}/redact", {"category": "health"}).status_code
        == 404
    )


def test_redact_erases_the_text_and_audits_only_the_category(
    api: TestClient, people: People, migrated_database: str
) -> None:
    # Etapa 17.5, CA-4 (FR-25): o texto some na mesma transação e a auditoria tem a categoria.
    attendant = _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    handoff_id = _request(visitor, conversation_id, answer_id).json()["id"]
    _post(attendant, f"/v1/attendance/handoffs/{handoff_id}/take", None)
    sent = _post(
        visitor,
        f"/v1/conversations/{conversation_id}/handoff/messages",
        {"text": "Estou com dor no peito", "client_message_id": str(uuid4())},
    ).json()
    redacted = _post(
        attendant,
        f"/v1/attendance/handoffs/{handoff_id}/messages/{sent['id']}/redact",
        {"category": "health"},
    )
    assert redacted.status_code == 200
    assert redacted.json()["redaction"] == "health"
    assert redacted.json()["seq"] > sent["seq"]
    assert _run(_handoff_contents(migrated_database, conversation_id)) == ["[mensagem removida]"]
    reasons = _run(_audit_reasons(migrated_database, UUID(handoff_id)))
    assert ("handoff.message_redact", "health") in reasons
    loaded = visitor.get(f"/v1/conversations/{conversation_id}").json()
    handoff_messages = [row for row in loaded["messages"] if row["handoff_id"]]
    assert handoff_messages[0]["redaction"] == "health"
    assert "dor no peito" not in str(loaded)


def test_staff_closes_only_with_a_reason_of_the_list(api: TestClient, people: People) -> None:
    # Etapa 17.5, CA-6 (FR-24) e a auditoria `handoff.close`.
    attendant = _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    handoff_id = _request(visitor, conversation_id, answer_id).json()["id"]
    _post(attendant, f"/v1/attendance/handoffs/{handoff_id}/take", None)
    reply = _post(
        attendant,
        f"/v1/attendance/handoffs/{handoff_id}/messages",
        {"template": "medical_emergency", "client_message_id": str(uuid4())},
    )
    assert reply.status_code == 201
    assert reply.json()["role"] == "attendant"
    invalid = _post(attendant, f"/v1/attendance/handoffs/{handoff_id}/close", {"reason": "cansei"})
    assert invalid.status_code == 422
    closed = _post(attendant, f"/v1/attendance/handoffs/{handoff_id}/close", {"reason": "resolved"})
    assert closed.json()["close_reason"] == "resolved"
    status = visitor.get(f"/v1/conversations/{conversation_id}/handoff").json()
    assert status["status"] == "closed"


def test_admin_reads_a_closed_handoff_only_with_a_reason(
    api: TestClient, people: People, migrated_database: str
) -> None:
    # Etapa 17.5, CA-5 (FR-26): sem motivo, 422 sem gravar; com motivo, `handoff.view`.
    attendant = _staff_ready(api, people)
    admin = _login(api, people.account("admin"))
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    handoff_id = _request(visitor, conversation_id, answer_id).json()["id"]
    _post(attendant, f"/v1/attendance/handoffs/{handoff_id}/take", None)
    _post(attendant, f"/v1/attendance/handoffs/{handoff_id}/close", {"reason": "resolved"})
    listed = admin.get("/v1/admin/handoffs?period_days=7").json()["handoffs"]
    assert any(row["id"] == handoff_id for row in listed)
    # A lista não tem o texto de nenhuma mensagem, só contagens e datas.
    assert all("content" not in row and "messages" not in row for row in listed)
    short = _post(admin, f"/v1/admin/handoffs/{handoff_id}/view", {"reason": "curto"})
    assert short.status_code == 422
    assert "reason" in short.json()["error"]["field_errors"]
    assert ("handoff.view", None) not in _run(_audit_reasons(migrated_database, UUID(handoff_id)))
    viewed = _post(
        admin,
        f"/v1/admin/handoffs/{handoff_id}/view",
        {"reason": "Reclamação registrada pelo visitante na ouvidoria"},
    )
    assert viewed.status_code == 200
    actions = [action for action, _ in _run(_audit_reasons(migrated_database, UUID(handoff_id)))]
    assert "handoff.view" in actions
    assert attendant.get("/v1/admin/handoffs").status_code == 403


def test_sweep_closes_the_old_queue_and_returns_the_handoff_of_who_left(
    api: TestClient,
    people: People,
    migrated_database: str,
    clock: MovingClock,
    broker: InMemoryBroker,
) -> None:
    # Etapa 17.4, CA-7, e Etapa 17.5, CA-7: espera vencida, quem atende sem sinal e duas
    # varreduras ao mesmo tempo sem efeito duplicado.
    attendant = _staff_ready(api, people)
    visitor, conversation_id, answer_id = _guest_conversation(api, people)
    assert _request(visitor, conversation_id, answer_id).status_code == 201
    other_visitor, other_id, other_answer = _guest_conversation(api, people)
    taken = _request(other_visitor, other_id, other_answer).json()["id"]
    _post(attendant, f"/v1/attendance/handoffs/{taken}/take", None)
    clock.advance(minutes=16)
    # O visitante do atendimento assumido continua na conversa: o fluxo dele mandou sinal.
    _run(_touch_visitor(migrated_database, UUID(taken), clock.now()))
    sweeper = HandoffSweeper(
        database_url=migrated_database, clock=clock, enabled=True, broker=broker
    )

    async def twice() -> list[dict[str, int]]:
        return list(await asyncio.gather(sweeper.sweep_once(), sweeper.sweep_once()))

    results = asyncio.run(twice())
    assert sum(result["queue_timeout"] for result in results) >= 1
    assert sum(result["attendant_gone"] for result in results) == 1
    waiting_now = visitor.get(f"/v1/conversations/{conversation_id}/handoff").json()
    assert waiting_now["close_reason"] in {"queue_timeout", "visitor_left"}
    returned = other_visitor.get(f"/v1/conversations/{other_id}/handoff").json()
    assert returned["status"] == "queued"


def _staff_ready(api: TestClient, people: People) -> TestClient:
    """Uma atendente que entrou, aceitou o compromisso e marcou Disponível."""
    client = _login(api, people.account("attendant"))
    _post(client, "/v1/attendance/acknowledgement", {"version": ATTENDANT_TERMS_VERSION})
    response = client.put(
        "/v1/attendance/presence", headers={"Origin": ORIGIN}, json={"status": "available"}
    )
    assert response.status_code == 200
    return client


def _guest_conversation(
    api: TestClient, people: People, *, outcome: str = "abstained"
) -> tuple[TestClient, UUID, UUID]:
    """Um convidado com uma conversa que termina numa resposta com o `outcome`."""
    visitor = TestClient(api.app)
    created = visitor.post("/v1/conversations", headers=_headers())
    assert created.status_code == 201
    secret = created.cookies.get("atrium_guest")
    assert isinstance(secret, str)
    people.guest_secrets.append(secret)
    conversation_id = UUID(created.json()["id"])
    answer_id = _run(_answer(people.database_url, conversation_id, outcome))
    return visitor, conversation_id, answer_id


async def _conversation_with_answer(
    visitor: TestClient, database_url: str, outcome: str
) -> tuple[UUID, UUID]:
    """Outra conversa do mesmo convidado, já com a resposta."""
    created = visitor.post("/v1/conversations", headers=_headers())
    conversation_id = UUID(created.json()["id"])
    return conversation_id, await _answer(database_url, conversation_id, outcome)


async def _answer(database_url: str, conversation_id: UUID, outcome: str) -> UUID:
    """Grava uma pergunta e a resposta do assistente com o desfecho, como o fluxo faria."""
    answer_id = uuid4()
    async with open_session(database_url) as session, UnitOfWork(session):
        repository = ConversationRepository(session)
        for role, content, message_id, result in (
            ("user", "Vocês têm heliponto?", uuid4(), None),
            ("assistant", "Não encontrei essa informação.", answer_id, outcome),
        ):
            await repository.insert_message(
                message_id=message_id,
                conversation_id=conversation_id,
                client_message_id=uuid4() if role == "user" else None,
                role=role,
                content=content,
                citations=(),
                model=None,
                prompt_version=None,
                input_tokens=0,
                output_tokens=0,
                latency_ms=None,
                outcome=result,
                langsmith_run_id=None,
                created_at=await repository.allocate_created_at(conversation_id, NOW),
            )
    return answer_id


def _request(client: TestClient, conversation_id: UUID, answer_id: UUID) -> Any:
    """`POST /v1/conversations/{id}/handoff` com a resposta que motivou o pedido."""
    return _post(
        client,
        f"/v1/conversations/{conversation_id}/handoff",
        {"trigger_message_id": str(answer_id)},
    )


def _login(api: TestClient, email: str) -> TestClient:
    """Um cliente com o pote de cookies da sessão de `email`."""
    client = TestClient(api.app)
    response = _post(client, "/v1/auth/login", {"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return client


def _post(client: TestClient, path: str, body: dict[str, object] | None) -> Any:
    """`POST` com o `Origin` certo e um IP único, para os baldes não colidirem."""
    return client.post(path, headers=_headers(), json=body)


def _headers() -> dict[str, str]:
    """`Origin` certo e um IP único por pedido."""
    return {"Origin": ORIGIN, "X-Forwarded-For": f"test-{uuid4().hex}"}


def _attendance(database_url: str, broker: InMemoryBroker) -> AttendanceService:
    """O serviço da equipe direto, para as corridas num loop só."""
    return AttendanceService(
        database_url=database_url,
        clock=MovingClock(NOW),
        hmac_key=HMAC_KEY,
        pseudonym_key=PSEUDONYM_KEY,
        broker=broker,
    )


def _app(client: TestClient) -> FastAPI:
    """O `FastAPI` por trás do `TestClient`."""
    application = client.app
    if not isinstance(application, FastAPI):
        raise AssertionError(type(application))
    return application


def _run[T](coroutine: Coroutine[Any, Any, T]) -> T:
    """Roda a corrotina num loop novo e devolve o resultado."""
    return asyncio.run(coroutine)


async def _revision(database_url: str) -> str:
    """A revisão do Alembic gravada no banco."""
    async with open_session(database_url) as session, UnitOfWork(session):
        value = await session.scalar(text("SELECT version_num FROM alembic_version"))
    return str(value)


async def _insert(database_url: str, email: str, role: str) -> None:
    """Grava a conta com a senha `PASSWORD` em argon2id."""
    async with open_session(database_url) as session, UnitOfWork(session):
        await UserRepository(session).insert(
            email=email,
            password_hash=get_password_hasher().hash_password(PASSWORD),
            full_name="Pessoa Teste",
            role=role,
            now=datetime.now(UTC),
        )


async def _role(database_url: str, email: str) -> str:
    """O papel gravado da conta."""
    async with open_session(database_url) as session, UnitOfWork(session):
        user = await UserRepository(session).get_by_email(email)
    assert user is not None
    return user.role


async def _staff_member(database_url: str, email: str) -> StaffMember:
    """A pessoa da equipe do e-mail, como a dependência `require_attendant` montaria."""
    async with open_session(database_url) as session, UnitOfWork(session):
        user = await UserRepository(session).get_by_email(email)
    assert user is not None
    return StaffMember(user_id=user.id, role=user.role)


async def _acknowledge(database_url: str, *staff: StaffMember) -> None:
    """Grava o aceite do compromisso vigente para cada pessoa."""
    async with open_session(database_url) as session, UnitOfWork(session):
        for member in staff:
            await HandoffRepository(session).acknowledge(
                member.user_id, ATTENDANT_TERMS_VERSION, NOW
            )


async def _actions(database_url: str, target_id: UUID) -> list[str]:
    """As ações de auditoria sobre o alvo, na ordem."""
    async with open_session(database_url) as session, UnitOfWork(session):
        rows = await session.scalars(
            select(AuditEvent.action)
            .where(AuditEvent.target_id == target_id)
            .order_by(AuditEvent.created_at.asc(), AuditEvent.action.asc())
        )
        return list(rows)


async def _audit_reasons(database_url: str, target_id: UUID) -> list[tuple[str, str | None]]:
    """As ações e os motivos de auditoria sobre o atendimento."""
    async with open_session(database_url) as session, UnitOfWork(session):
        rows = await session.execute(
            select(AuditEvent.action, AuditEvent.reason).where(AuditEvent.target_id == target_id)
        )
        return [(str(action), reason) for action, reason in rows]


async def _touch_visitor(database_url: str, handoff_id: UUID, now: datetime) -> None:
    """O sinal do fluxo do visitante, como o tique gravaria."""
    async with open_session(database_url) as session, UnitOfWork(session):
        await HandoffRepository(session).touch_visitor(handoff_id, now)


async def _handoff_contents(database_url: str, conversation_id: UUID) -> list[str]:
    """O texto gravado das mensagens do atendimento da conversa, por `seq`."""
    async with open_session(database_url) as session, UnitOfWork(session):
        rows = await session.scalars(
            select(Message.content)
            .where(Message.conversation_id == conversation_id, Message.handoff_id.is_not(None))
            .order_by(Message.seq.asc())
        )
        return list(rows)
