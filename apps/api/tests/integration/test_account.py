"""Conta do membro: perfil, exportação, consentimentos e exclusão. FR-9 e NFR-12.

Seções 11.5, 11.6 e 12 do SDD, critérios CA-1 a CA-5 da Etapa 6.1. O `TestClient` chama a API
real com `APP_AI_ADAPTER=fake` e o relógio `FrozenClock`. `_seed_member` e
`_seed_conversation` gravam o membro, os aceites e uma troca com citação e feedback pelos
repositórios, e `_purge` apaga tudo pelo e-mail no fim. Precisa de PostgreSQL com pgvector local
(`migrated_database`); sem ele pula, e com `REQUIRE_INTEGRATION_DB=1` falha.
"""

import asyncio
import json
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.adapters.password_hasher import get_password_hasher
from app.core.container import get_clock, get_settings
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.grounding import Citation
from app.domain.legal import LEGAL_DOCUMENT_VERSION
from app.domain.registration import ConsentGrant, Purpose
from app.main import create_app
from app.models.audit_event import AuditEvent
from app.models.auth_session import AuthSession
from app.models.consent_record import ConsentRecord
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.consents import ConsentRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.users import UserRepository

pytestmark = pytest.mark.integration

ORIGIN = "http://localhost:5173"
HMAC_KEY = "test-hmac-key"
PASSWORD = "correct-horse-1"
FIXED = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
LEGAL = LEGAL_DOCUMENT_VERSION


class FrozenClock:
    """Relógio parado em `FIXED`, no lugar de `get_clock`."""

    def now(self) -> datetime:
        return FIXED


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch, migrated_database: str) -> TestClient:
    """API real com `APP_AI_ADAPTER=fake`, o relógio parado e o banco migrado."""
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", HMAC_KEY)
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_AI_ADAPTER", "fake")
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_clock] = FrozenClock
    return TestClient(application)


def test_patch_me_persists_the_name_and_rejects_the_email(
    api: TestClient, migrated_database: str
) -> None:
    email = _email("patch")
    try:
        _run(_seed_member(migrated_database, email=email))
        _login(api, email)
        changed = api.patch("/v1/me", headers=_headers(), json={"full_name": "Maria Nova"})
        assert changed.status_code == 200
        assert changed.json()["full_name"] == "Maria Nova"
        assert api.get("/v1/me").json()["full_name"] == "Maria Nova"
        refused = api.patch("/v1/me", headers=_headers(), json={"email": "outro@example.com"})
        assert refused.status_code == 422
        too_short = api.patch("/v1/me", headers=_headers(), json={"full_name": "M"})
        assert too_short.status_code == 422
        assert "full_name" in too_short.json()["error"]["field_errors"]
    finally:
        _run(_purge(migrated_database, email))


def test_sensitive_fields_need_personalization_and_revoking_clears_them(
    api: TestClient, migrated_database: str
) -> None:
    email = _email("personalization")
    try:
        _run(_seed_member(migrated_database, email=email))
        _login(api, email)
        blocked = api.patch("/v1/me", headers=_headers(), json={"visitor_type": "patient"})
        assert blocked.status_code == 422
        assert "visitor_type" in blocked.json()["error"]["field_errors"]

        granted = api.put(
            f"/v1/me/consents/{Purpose.PERSONALIZATION.value}",
            headers=_headers(),
            json={"granted": True},
        )
        assert granted.status_code == 200
        saved = api.patch(
            "/v1/me",
            headers=_headers(),
            json={"visitor_type": "patient", "visit_reason": "own_appointment"},
        )
        assert saved.status_code == 200
        assert saved.json()["visitor_type"] == "patient"

        revoked = api.put(
            f"/v1/me/consents/{Purpose.PERSONALIZATION.value}",
            headers=_headers(),
            json={"granted": False},
        )
        assert revoked.status_code == 200
        state = {item["purpose"]: item["granted"] for item in revoked.json()["current"]}
        assert state[Purpose.PERSONALIZATION.value] is False
        assert _run_value(_read_sensitive(migrated_database, email)) == (None, None)
        assert api.get("/v1/me").json()["visit_reason"] is None
    finally:
        _run(_purge(migrated_database, email))


def test_consents_keep_history_and_protect_the_mandatory_ones(
    api: TestClient, migrated_database: str
) -> None:
    email = _email("consents")
    purpose = Purpose.QUALITY.value
    try:
        _run(_seed_member(migrated_database, email=email))
        _login(api, email)
        for granted in (True, False, True):
            api.put(f"/v1/me/consents/{purpose}", headers=_headers(), json={"granted": granted})
        listing = api.get("/v1/me/consents")
        assert listing.status_code == 200
        quality = [item for item in listing.json()["history"] if item["purpose"] == purpose]
        assert len(quality) == 2
        assert sum(item["revoked_at"] is None for item in quality) == 1
        assert {item["source"] for item in quality} == {"account"}
        for blocked, granted in (
            (Purpose.TERMS.value, False),
            (Purpose.AGE.value, True),
            (Purpose.AGE.value, False),
            ("unknown", True),
        ):
            response = api.put(
                f"/v1/me/consents/{blocked}", headers=_headers(), json={"granted": granted}
            )
            assert response.status_code == 422, (blocked, granted)
    finally:
        _run(_purge(migrated_database, email))


def test_export_has_profile_consents_conversations_citations_and_feedback_only(
    api: TestClient, migrated_database: str
) -> None:
    email = _email("export")
    other = _email("other")
    try:
        _run(_seed_member(migrated_database, email=email))
        _run(_seed_member(migrated_database, email=other))
        _run(_seed_conversation(migrated_database, email=email, text="PERGUNTA-DO-TITULAR"))
        _run(_seed_conversation(migrated_database, email=other, text="PERGUNTA-DE-OUTRO"))
        _login(api, email)
        response = api.get("/v1/me/export")
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
        body = response.json()
        assert body["profile"]["email"] == email
        assert {item["purpose"] for item in body["consents"]} >= {
            Purpose.TERMS.value,
            Purpose.AGE.value,
        }
        assert all(item["document_version"] for item in body["consents"])
        assert len(body["conversations"]) == 1
        messages = body["conversations"][0]["messages"]
        assert [item["role"] for item in messages] == ["user", "assistant"]
        assert messages[0]["content"] == "PERGUNTA-DO-TITULAR"
        assert messages[1]["citations"] == [
            {"index": 1, "document_title": "Horário de visita", "heading": "Visitas"}
        ]
        assert messages[1]["feedback"] == 1
        raw = json.dumps(body)
        assert "PERGUNTA-DE-OUTRO" not in raw
        assert other not in raw
        for forbidden in ("password", "hash", "langsmith", "token", "chunk_id"):
            assert forbidden not in raw.lower()
    finally:
        _run(_purge(migrated_database, email))
        _run(_purge(migrated_database, other))


def test_delete_removes_everything_revokes_the_session_and_audits_only_the_id(
    api: TestClient, migrated_database: str
) -> None:
    email = _email("delete")
    user_id: UUID | None = None
    try:
        _run(_seed_member(migrated_database, email=email))
        _run(_seed_conversation(migrated_database, email=email, text="apagar"))
        _login(api, email)
        user_id = _run_value(_user_id(migrated_database, email))
        assert user_id is not None

        response = api.delete("/v1/me", headers=_headers())
        assert response.status_code == 204
        assert "atrium_session" in response.headers["set-cookie"]
        counts = _run_value(_counts(migrated_database, user_id))
        assert counts == {"users": 0, "consents": 0, "conversations": 0, "sessions": 0}
        assert api.get("/v1/me").status_code == 401

        events = _run_value(_audit_events(migrated_database, user_id))
        assert events == [("account.delete", "user", user_id, None)]
        # Semear de novo com o mesmo e-mail só passa se a exclusão liberou o e-mail único.
        _run(_seed_member(migrated_database, email=email))
    finally:
        _run(_purge(migrated_database, email))
        if user_id is not None:
            _run(_purge_audit(migrated_database, user_id))


def test_an_admin_cannot_delete_the_own_account(api: TestClient, migrated_database: str) -> None:
    email = _email("admin")
    try:
        _run(_seed_member(migrated_database, email=email, role="admin"))
        _login(api, email)
        response = api.delete("/v1/me", headers=_headers())
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"
        assert api.get("/v1/me").status_code == 200
    finally:
        _run(_purge(migrated_database, email))


def test_new_legal_version_is_accepted_through_the_consent_endpoint(
    api: TestClient, migrated_database: str
) -> None:
    email = _email("legal")
    try:
        _run(_seed_member(migrated_database, email=email, terms_version="2025-01-01.1"))
        _login(api, email)
        assert api.get("/v1/me").json()["needs_legal_acceptance"] is True
        accepted = api.put(
            f"/v1/me/consents/{Purpose.TERMS.value}",
            headers=_headers(),
            json={"granted": True},
        )
        assert accepted.status_code == 200
        assert api.get("/v1/me").json()["needs_legal_acceptance"] is False
    finally:
        _run(_purge(migrated_database, email))


def test_conversation_list_shows_the_first_question(
    api: TestClient, migrated_database: str
) -> None:
    email = _email("list")
    try:
        _run(_seed_member(migrated_database, email=email))
        _run(_seed_conversation(migrated_database, email=email, text="Qual o horário de visita?"))
        _login(api, email)
        listed = api.get("/v1/conversations")
        assert listed.status_code == 200
        items = listed.json()["conversations"]
        assert [item["first_question"] for item in items] == ["Qual o horário de visita?"]
    finally:
        _run(_purge(migrated_database, email))


def test_account_routes_require_a_session_and_the_origin(api: TestClient) -> None:
    assert api.patch("/v1/me", headers=_headers(), json={"full_name": "Ana"}).status_code == 401
    assert api.get("/v1/me/export").status_code == 401
    assert api.get("/v1/me/consents").status_code == 401
    assert api.delete("/v1/me", headers=_headers()).status_code == 401
    # Sem `Origin`, o pedido recebe 403 antes de a sessão ser conferida (NFR-12).
    assert api.delete("/v1/me").status_code == 403


def _headers() -> dict[str, str]:
    """Cabeçalho `Origin` que os pedidos de mudança de estado exigem (NFR-12)."""
    return {"Origin": ORIGIN}


def _login(client: TestClient, email: str) -> None:
    """Entra com `PASSWORD` de um IP único. O cookie fica no pote do cliente."""
    response = client.post(
        "/v1/auth/login",
        headers={"Origin": ORIGIN, "X-Forwarded-For": f"test-{uuid4().hex}"},
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text


def _email(label: str) -> str:
    """E-mail único por chamada, para os testes não colidirem no banco compartilhado."""
    return f"{label}-{uuid4().hex}@example.com"


def _run(coro: Coroutine[object, object, None]) -> None:
    """Roda a corrotina num loop novo e descarta o resultado."""
    asyncio.run(coro)


def _run_value(coro: Coroutine[object, object, Any]) -> Any:
    """Roda a corrotina num loop novo e devolve o resultado."""
    return asyncio.run(coro)


async def _seed_member(
    database_url: str,
    *,
    email: str,
    role: str = "member",
    terms_version: str = LEGAL,
) -> None:
    """Grava um usuário com os aceites dos Termos e da maioridade em `terms_version`."""
    async with open_session(database_url) as session, UnitOfWork(session):
        user_id = await UserRepository(session).insert(
            email=email,
            password_hash=get_password_hasher().hash_password(PASSWORD),
            full_name="Visitante Teste",
            role=role,
            now=FIXED,
        )
        await ConsentRepository(session).insert_grants(
            user_id=user_id,
            grants=(
                ConsentGrant(Purpose.TERMS.value, terms_version),
                ConsentGrant(Purpose.AGE.value, terms_version),
            ),
            source="form",
            granted_at=FIXED,
        )


async def _seed_conversation(database_url: str, *, email: str, text: str) -> None:
    """Grava numa conversa do membro a pergunta `text` e uma resposta citada com feedback útil."""
    async with open_session(database_url) as session, UnitOfWork(session):
        user = await UserRepository(session).get_by_email(email)
        assert user is not None
        conversations = ConversationRepository(session)
        conversation = await conversations.insert_conversation(
            user_id=user.id, guest_key_id=None, created_at=FIXED
        )
        answered = uuid4()
        await conversations.insert_message(
            message_id=uuid4(),
            conversation_id=conversation.id,
            client_message_id=uuid4(),
            role="user",
            content=text,
            citations=(),
            model=None,
            prompt_version=None,
            input_tokens=0,
            output_tokens=0,
            latency_ms=None,
            outcome=None,
            langsmith_run_id=None,
            created_at=FIXED,
        )
        await conversations.insert_message(
            message_id=answered,
            conversation_id=conversation.id,
            client_message_id=None,
            role="assistant",
            content="Resposta [1]",
            citations=(
                Citation(
                    index=1,
                    document_title="Horário de visita",
                    heading="Visitas",
                    chunk_id=uuid4(),
                ),
            ),
            model="fake",
            prompt_version="v1",
            input_tokens=1,
            output_tokens=1,
            latency_ms=5,
            outcome="answered",
            langsmith_run_id=uuid4(),
            created_at=datetime(2026, 11, 3, 12, 0, 1, tzinfo=UTC),
        )
        await conversations.insert_feedback(answered, 1, FIXED)


async def _user_id(database_url: str, email: str) -> UUID | None:
    """Id do usuário com este e-mail, ou `None`."""
    async with open_session(database_url) as session:
        return await session.scalar(select(User.id).where(User.email == email))


async def _read_sensitive(database_url: str, email: str) -> tuple[str | None, str | None]:
    """Lê `visitor_type` e `visit_reason` direto da tabela `users`."""
    async with open_session(database_url) as session:
        row = (
            await session.execute(
                select(User.visitor_type, User.visit_reason).where(User.email == email)
            )
        ).one()
    return row[0], row[1]


async def _counts(database_url: str, user_id: UUID) -> dict[str, int]:
    """Conta as linhas do usuário que a exclusão precisa apagar."""
    queries = {
        "users": select(func.count()).select_from(User).where(User.id == user_id),
        "consents": select(func.count())
        .select_from(ConsentRecord)
        .where(ConsentRecord.user_id == user_id),
        "conversations": select(func.count())
        .select_from(Conversation)
        .where(Conversation.user_id == user_id),
        "sessions": select(func.count())
        .select_from(AuthSession)
        .where(AuthSession.user_id == user_id),
    }
    async with open_session(database_url) as session:
        return {name: int(await session.scalar(query) or 0) for name, query in queries.items()}


async def _audit_events(
    database_url: str, user_id: UUID
) -> list[tuple[str, str, UUID, str | None]]:
    """Eventos de auditoria com este usuário como ator."""
    async with open_session(database_url) as session:
        rows = await session.execute(
            select(
                AuditEvent.action,
                AuditEvent.target_type,
                AuditEvent.target_id,
                AuditEvent.reason,
            ).where(AuditEvent.actor_user_id == user_id)
        )
        return [(action, kind, target, reason) for action, kind, target, reason in rows]


async def _purge_audit(database_url: str, user_id: UUID) -> None:
    """Apaga a auditoria do usuário, que sobrevive à exclusão da conta (seção 11.6)."""
    async with open_session(database_url) as session, UnitOfWork(session):
        await session.execute(delete(AuditEvent).where(AuditEvent.actor_user_id == user_id))


async def _purge(database_url: str, email: str) -> None:
    """Apaga o usuário pelo e-mail, com as mensagens, as sessões e a auditoria dele.

    Consentimentos e conversas caem em cascata com o usuário.
    """
    async with open_session(database_url) as session, UnitOfWork(session):
        users = UserRepository(session)
        user = await users.get_by_email(email)
        if user is None:
            return
        await session.execute(
            delete(Message).where(
                Message.conversation_id.in_(
                    select(Conversation.id).where(Conversation.user_id == user.id)
                )
            )
        )
        await AuthSessionRepository(session).delete_for_user(user.id)
        await session.execute(delete(AuditEvent).where(AuditEvent.actor_user_id == user.id))
        await users.delete_user(user.id)
