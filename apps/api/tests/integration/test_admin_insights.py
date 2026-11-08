"""Visão geral, qualidade, inspetor e revelação do admin. FR-15, NFR-10 e seção 11.8 do SDD.

Seções 12 e 15.5 do SDD, critérios CA-1 e CA-2 da Etapa 7.2. A fixture `world` grava em SQL
cru o cenário de `_build`: um admin, um membro que consentiu a melhoria, outro que revogou,
um convidado, cinco conversas, feedback, sessões de cadastro e o uso de tokens do dia. O
relógio fica em 2031 para os agregados só verem os dados deste teste, mesmo num banco
compartilhado. `_cleanup` apaga tudo pelos ids. Precisa de PostgreSQL com pgvector local
(`migrated_database`); sem ele pula, e com `REQUIRE_INTEGRATION_DB=1` falha.
"""

import asyncio
import hashlib
from collections.abc import Coroutine, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.adapters.password_hasher import get_password_hasher
from app.core.container import get_clock, get_settings
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.legal import LEGAL_DOCUMENT_VERSION
from app.domain.registration import REGISTRATION_TTL
from app.main import create_app
from app.prompts.insights import CONVERSATION_HIDDEN

pytestmark = pytest.mark.integration

ORIGIN = "http://localhost:5173"
HMAC_KEY = "test-hmac-key"
PSEUDONYM_KEY = "test-pseudonym-key"
PASSWORD = "correct-horse-1"
NOW = datetime(2031, 1, 15, 12, 0, tzinfo=UTC)
TEMPLATE = "https://smith.example/r/{run_id}"
BUDGET = 1000


class FrozenClock:
    """Relógio parado em `NOW`, em 2031, longe dos dados dos outros testes."""

    def now(self) -> datetime:
        return NOW


@dataclass
class _World:
    """Ids do cenário que `_build` grava, com o cliente do admin logado."""

    client: TestClient
    database_url: str
    admin_id: UUID
    users: list[UUID]
    guest_key: UUID
    guest_conversation: UUID
    consenting_conversation: UUID
    hidden_conversation: UUID
    old_conversation: UUID
    first_answer: UUID
    registrations: list[UUID]


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, migrated_database: str) -> Iterator[_World]:
    """API com o relógio em 2031, o cenário de `_build` gravado e o admin logado.

    O teto de tokens fica em `BUDGET` e o `LANGSMITH_RUN_URL_TEMPLATE` aponta para um host falso,
    para a visão geral ter `ratio` e o inspetor ter `trace_url`. `_cleanup` apaga tudo no fim.
    """
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", HMAC_KEY)
    monkeypatch.setenv("PSEUDONYM_KEY", PSEUDONYM_KEY)
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_AI_ADAPTER", "fake")
    monkeypatch.setenv("LLM_DAILY_TOKEN_BUDGET", str(BUDGET))
    monkeypatch.setenv("LANGSMITH_RUN_URL_TEMPLATE", TEMPLATE)
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_clock] = FrozenClock
    built = _run(_build(migrated_database))
    client = TestClient(application)
    _login(client, built["admin_email"])
    try:
        yield _World(client=client, database_url=migrated_database, **built["ids"])
    finally:
        _run(_cleanup(migrated_database, built))
        get_settings.cache_clear()


def test_overview_compares_with_the_previous_period(world: _World) -> None:
    response = world.client.get("/v1/admin/overview?period_days=7")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["period_days"] == 7
    # Atual: 4 perguntas (guest 2, consenting 1, hidden 1). Anterior: 1 pergunta.
    assert body["questions"] == {"current": 4.0, "previous": 1.0}
    # Desfechos atuais: answered 2, abstained 1, refused 1.
    assert body["answer_rate"]["current"] == 0.5
    assert body["abstention_rate"]["current"] == 0.25
    assert body["answer_rate"]["previous"] == 1.0
    # Feedback atual: um útil, um não útil.
    assert body["helpful_rate"]["current"] == 0.5
    assert body["helpful_rate"]["previous"] is None
    assert body["outcomes"]["answered"] == 2
    assert body["outcomes"]["grounding_failed"] == 0
    assert body["intents"] == {"public_info": 3, "medical_advice": 1, "off_topic": 0}
    assert body["feedback"] == {"helpful": 1, "not_helpful": 1, "none": 2}
    assert len(body["trend"]) == 8
    assert body["trend"][-1] == {"date": "2031-01-15", "questions": 4, "answered": 2}
    assert sum(point["questions"] for point in body["trend"]) == 4
    funnel = {row["step"]: row for row in body["funnel"]}
    assert funnel["started"] == {"step": "started", "chat": 2, "form": 1}
    assert funnel["password_set"]["chat"] == 1
    assert funnel["completed"] == {"step": "completed", "chat": 1, "form": 1}
    assert body["budget"] == {"used_tokens": 850, "daily_budget": BUDGET, "ratio": 0.85}


def test_quality_lists_only_guests_and_consenting_members(world: _World) -> None:
    """CA-2: sem o consentimento de melhoria, a conversa fica só nos agregados."""
    response = world.client.get("/v1/admin/quality?period_days=7")
    assert response.status_code == 200, response.text
    body = response.json()
    ids = [item["id"] for item in body["conversations"]]
    assert set(ids) == {str(world.guest_conversation), str(world.consenting_conversation)}
    assert body["outcomes"]["refused"] == 1  # a conversa oculta conta no agregado
    guest = next(i for i in body["conversations"] if i["id"] == str(world.guest_conversation))
    assert guest["subject_kind"] == "guest"
    assert len(guest["pseudonym"]) == 8
    assert guest["questions"] == 2
    assert guest["helpful"] == 1
    assert guest["last_outcome"] == "abstained"
    assert "email" not in guest

    unhelpful = world.client.get("/v1/admin/quality?period_days=7&feedback=not_helpful").json()
    assert [item["id"] for item in unhelpful["conversations"]] == [
        str(world.consenting_conversation)
    ]
    abstained = world.client.get("/v1/admin/quality?period_days=7&outcome=abstained").json()
    assert [item["id"] for item in abstained["conversations"]] == [str(world.guest_conversation)]
    month = world.client.get("/v1/admin/quality?period_days=30").json()
    assert str(world.old_conversation) in [item["id"] for item in month["conversations"]]
    assert world.client.get("/v1/admin/quality?period_days=14").status_code == 422
    assert world.client.get("/v1/admin/quality?outcome=bogus").status_code == 422


def test_opening_a_conversation_records_conversation_view(world: _World) -> None:
    """CA-1, parte 1."""
    response = world.client.get(f"/v1/admin/conversations/{world.guest_conversation}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["subject_kind"] == "guest"
    assert [message["role"] for message in body["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    answer = body["messages"][1]
    assert answer["prompt_version"] == "qa-v1"
    assert answer["request_id"] == "req-1"
    assert answer["run_id"] == str(world.first_answer)
    assert answer["trace_url"] == f"https://smith.example/r/{world.first_answer}"
    assert answer["rating"] == 1
    assert answer["citations"] == [{"index": 1, "document_title": "Visitas", "heading": "Horário"}]
    assert _run(_audit(world.database_url, world.admin_id)) == [
        ("conversation.view", str(world.guest_conversation), None)
    ]


def test_a_hidden_conversation_is_404_and_not_audited(world: _World) -> None:
    """CA-2: o inspetor não abre membro sem consentimento de melhoria."""
    response = world.client.get(f"/v1/admin/conversations/{world.hidden_conversation}")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == CONVERSATION_HIDDEN
    reveal = world.client.post(
        f"/v1/admin/conversations/{world.hidden_conversation}/reveal",
        headers={"Origin": ORIGIN},
        json={"reason": "Pedido de titular número 12"},
    )
    assert reveal.status_code == 404
    assert _run(_audit(world.database_url, world.admin_id)) == []


def test_revealing_needs_a_reason_and_records_identity_reveal(world: _World) -> None:
    """CA-1, parte 2 (FR-15)."""
    url = f"/v1/admin/conversations/{world.consenting_conversation}/reveal"
    short = world.client.post(url, headers={"Origin": ORIGIN}, json={"reason": "porque"})
    assert short.status_code == 422
    assert "reason" in short.json()["error"]["field_errors"]
    assert _run(_audit(world.database_url, world.admin_id)) == []

    reason = "Pedido de titular número 12"
    revealed = world.client.post(url, headers={"Origin": ORIGIN}, json={"reason": reason})
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["full_name"] == "Membro Consentiu"
    assert revealed.json()["email"].startswith("insights-yes-")
    assert _run(_audit(world.database_url, world.admin_id)) == [
        ("identity.reveal", str(world.consenting_conversation), reason)
    ]
    guest = world.client.post(
        f"/v1/admin/conversations/{world.guest_conversation}/reveal",
        headers={"Origin": ORIGIN},
        json={"reason": reason},
    )
    assert guest.status_code == 409


def test_a_member_gets_403_on_insight_routes(world: _World) -> None:
    member = TestClient(world.client.app)
    email = _run(_email_of(world.database_url, world.users[1]))
    _login(member, email)
    target = world.guest_conversation
    calls = [
        member.get("/v1/admin/overview"),
        member.get("/v1/admin/quality"),
        member.get(f"/v1/admin/conversations/{target}"),
        member.post(
            f"/v1/admin/conversations/{target}/reveal",
            headers={"Origin": ORIGIN},
            json={"reason": "Pedido de titular número 12"},
        ),
    ]
    assert [call.status_code for call in calls] == [403] * 4
    assert TestClient(world.client.app).get("/v1/admin/overview").status_code == 401


def _login(client: TestClient, email: str) -> None:
    """Entra com `PASSWORD` de um IP único. O cookie fica no pote do cliente."""
    response = client.post(
        "/v1/auth/login",
        headers={"Origin": ORIGIN, "X-Forwarded-For": f"insights-{uuid4().hex}"},
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text


def _run(coro: Coroutine[object, object, Any]) -> Any:
    """Roda a corrotina num loop novo e devolve o resultado."""
    return asyncio.run(coro)


async def _exec(session: Any, sql: str, **params: Any) -> None:
    """Executa um SQL cru com parâmetros nomeados."""
    await session.execute(text(sql), params)


async def _build(database_url: str) -> dict[str, Any]:
    """Grava o cenário em SQL cru, numa transação, e devolve os ids.

    - `conv_guest`, do convidado: duas perguntas no período, `answered` com citação e feedback
      útil, e `abstained`.
    - `conv_yes`, do membro com o consentimento de melhoria: `answered` com feedback não útil.
    - `conv_no`, do membro que revogou o consentimento: `refused`, só nos agregados.
    - `conv_old`, do membro com o consentimento, há 20 dias: só no período de 30 dias.
    - `conv_previous`, do convidado, há 10 dias: o período anterior da visão de 7 dias.

    Mais três sessões de cadastro (chat concluída, chat no começo e formulário concluído) e 850
    tokens no dia, de um teto de 1.000.
    """
    tag = uuid4().hex
    hashed = get_password_hasher().hash_password(PASSWORD)
    admin, yes, no = uuid4(), uuid4(), uuid4()
    guest_key = uuid4()
    conv_guest, conv_yes, conv_no, conv_old, conv_previous = (uuid4() for _ in range(5))
    first_answer = uuid4()
    registrations = [uuid4() for _ in range(3)]
    async with open_session(database_url) as session, UnitOfWork(session):
        for user_id, email, name, role in (
            (admin, f"insights-admin-{tag}@example.com", "Admin", "admin"),
            (yes, f"insights-yes-{tag}@example.com", "Membro Consentiu", "member"),
            (no, f"insights-no-{tag}@example.com", "Membro Recusou", "member"),
        ):
            await _exec(
                session,
                "INSERT INTO users (id, email, password_hash, full_name, role, created_at, "
                "updated_at) VALUES (:id, :email, :hash, :name, :role, :now, :now)",
                id=user_id, email=email, hash=hashed, name=name, role=role, now=NOW,
            )
            await _consent(session, user_id, "terms_and_privacy_notice")
        await _consent(session, yes, "quality_improvement")
        await _consent(session, no, "quality_improvement", revoked=True)
        await _exec(
            session,
            "INSERT INTO guest_keys (id, token_hash, created_at) VALUES (:id, :hash, :now)",
            id=guest_key, hash=hashlib.sha256(tag.encode()).hexdigest(), now=NOW,
        )
        hour = timedelta(hours=1)
        owners: tuple[tuple[UUID, UUID | None, UUID | None, datetime], ...] = (
            (conv_guest, None, guest_key, NOW - 2 * hour),
            (conv_yes, yes, None, NOW - 3 * hour),
            (conv_no, no, None, NOW - 4 * hour),
            (conv_old, yes, None, NOW - timedelta(days=20)),
            (conv_previous, None, guest_key, NOW - timedelta(days=10)),
        )
        for conversation, owner_id, guest, started in owners:
            await _exec(
                session,
                "INSERT INTO conversations (id, user_id, guest_key_id, created_at) "
                "VALUES (:id, :user_id, :guest, :at)",
                id=conversation, user_id=owner_id, guest=guest, at=started,
            )
        second = timedelta(seconds=1)
        guest_second_answer = uuid4()
        yes_answer = uuid4()
        messages = [
            (uuid4(), conv_guest, "user", "Horário de visita?", None, NOW - 2 * hour),
            (first_answer, conv_guest, "assistant", "11h às 20h [1]", "answered",
             NOW - 2 * hour + second),
            (uuid4(), conv_guest, "user", "E aos domingos?", None, NOW - hour),
            (guest_second_answer, conv_guest, "assistant", "Não encontrei.", "abstained",
             NOW - hour + second),
            (uuid4(), conv_yes, "user", "Onde estaciono?", None, NOW - 3 * hour),
            (yes_answer, conv_yes, "assistant", "No subsolo.", "answered",
             NOW - 3 * hour + second),
            (uuid4(), conv_no, "user", "[orientação médica omitida]", None, NOW - 4 * hour),
            (uuid4(), conv_no, "assistant", "Não posso orientar.", "refused",
             NOW - 4 * hour + second),
            (uuid4(), conv_old, "user", "Lanchonete?", None, NOW - timedelta(days=20)),
            (uuid4(), conv_previous, "user", "Farmácia?", None, NOW - timedelta(days=10)),
            (uuid4(), conv_previous, "assistant", "Térreo.", "answered",
             NOW - timedelta(days=10) + second),
        ]
        for message_id, conversation, role, content, outcome, at in messages:
            is_first = message_id == first_answer
            await _exec(
                session,
                "INSERT INTO messages (id, conversation_id, role, content, citations, model, "
                "prompt_version, input_tokens, output_tokens, outcome, langsmith_run_id, "
                "request_id, created_at) VALUES (:id, :conversation, :role, :content, "
                "CAST(:citations AS jsonb), :model, :prompt, 0, 0, :outcome, :run, :request, :at)",
                id=message_id,
                conversation=conversation,
                role=role,
                content=content,
                citations=(
                    '[{"index": 1, "document_title": "Visitas", "heading": "Horário", '
                    '"chunk_id": "00000000-0000-4000-8000-000000000001"}]'
                    if is_first
                    else "[]"
                ),
                model="fake" if role == "assistant" else None,
                prompt="qa-v1" if role == "assistant" else None,
                outcome=outcome,
                run=message_id if role == "assistant" else None,
                request="req-1" if is_first else None,
                at=at,
            )
        for message_id, rating in ((first_answer, 1), (yes_answer, -1)):
            await _exec(
                session,
                "INSERT INTO feedback (message_id, rating, created_at) VALUES (:id, :r, :now)",
                id=message_id, r=rating, now=NOW,
            )
        for session_id, path, status, password in (
            (registrations[0], "chat", "completed", None),
            (registrations[1], "chat", "collecting_required", None),
            (registrations[2], "form", "completed", None),
        ):
            await _exec(
                session,
                "INSERT INTO registration_sessions (id, status, path, fields, password_hash, "
                "transcript, expires_at) VALUES (:id, :status, :path, '{}'::jsonb, :password, "
                "'[]'::jsonb, :expires)",
                id=session_id, status=status, path=path, password=password,
                expires=NOW - 5 * hour + REGISTRATION_TTL,
            )
        await _exec(
            session,
            "INSERT INTO token_usage_days (day, input_tokens, output_tokens) "
            "VALUES (:day, 600, 250) ON CONFLICT (day) DO UPDATE "
            "SET input_tokens = 600, output_tokens = 250",
            day=NOW.date(),
        )
    return {
        "admin_email": f"insights-admin-{tag}@example.com",
        "ids": {
            "admin_id": admin,
            "users": [admin, yes, no],
            "guest_key": guest_key,
            "guest_conversation": conv_guest,
            "consenting_conversation": conv_yes,
            "hidden_conversation": conv_no,
            "old_conversation": conv_old,
            "first_answer": first_answer,
            "registrations": registrations,
        },
        "conversations": [conv_guest, conv_yes, conv_no, conv_old, conv_previous],
    }


async def _consent(session: Any, user_id: UUID, purpose: str, *, revoked: bool = False) -> None:
    """Grava um consentimento na versão vigente, há 60 dias, revogado ontem se `revoked`."""
    await _exec(
        session,
        "INSERT INTO consent_records (user_id, purpose, document_version, granted_at, "
        "revoked_at, source) VALUES (:user_id, :purpose, :version, :now, :revoked, 'form')",
        user_id=user_id,
        purpose=purpose,
        version=LEGAL_DOCUMENT_VERSION,
        now=NOW - timedelta(days=60),
        revoked=NOW - timedelta(days=1) if revoked else None,
    )


async def _audit(database_url: str, actor: UUID) -> list[tuple[str, str, str | None]]:
    """Eventos de auditoria do ator: ação, alvo e motivo, na ordem de gravação."""
    async with open_session(database_url) as session:
        result = await session.execute(
            text(
                "SELECT action, target_id::text, reason FROM audit_events "
                "WHERE actor_user_id = :actor ORDER BY created_at, action"
            ),
            {"actor": actor},
        )
    return [(str(row[0]), str(row[1]), row[2]) for row in result.all()]


async def _email_of(database_url: str, user_id: UUID) -> str:
    """E-mail do usuário com este id."""
    async with open_session(database_url) as session:
        value = await session.scalar(
            text("SELECT email FROM users WHERE id = :id"), {"id": user_id}
        )
    return str(value)


async def _cleanup(database_url: str, built: dict[str, Any]) -> None:
    """Apaga o cenário pelos ids gravados em `_build`, os filhos antes dos pais."""
    ids = built["ids"]
    async with open_session(database_url) as session, UnitOfWork(session):
        conversations = built["conversations"]
        await _exec(
            session,
            "DELETE FROM feedback WHERE message_id IN (SELECT id FROM messages "
            "WHERE conversation_id = ANY(:ids))",
            ids=conversations,
        )
        await _exec(
            session, "DELETE FROM messages WHERE conversation_id = ANY(:ids)", ids=conversations
        )
        await _exec(session, "DELETE FROM conversations WHERE id = ANY(:ids)", ids=conversations)
        await _exec(session, "DELETE FROM guest_keys WHERE id = :id", id=ids["guest_key"])
        await _exec(
            session,
            "DELETE FROM registration_sessions WHERE id = ANY(:ids)",
            ids=ids["registrations"],
        )
        await _exec(session, "DELETE FROM token_usage_days WHERE day = :day", day=NOW.date())
        for user_id in ids["users"]:
            await _exec(session, "DELETE FROM audit_events WHERE actor_user_id = :id", id=user_id)
            await _exec(session, "DELETE FROM auth_sessions WHERE user_id = :id", id=user_id)
            await _exec(session, "DELETE FROM consent_records WHERE user_id = :id", id=user_id)
            await _exec(session, "DELETE FROM users WHERE id = :id", id=user_id)
