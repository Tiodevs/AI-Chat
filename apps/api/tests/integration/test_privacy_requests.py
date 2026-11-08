"""Canal do titular: prazo de 15 dias, limite por IP e validação. FR-16 e NFR-12.

Seções 8.1, 10.4, 11.5 e 12 do SDD, critério CA-2 da Etapa 6.2. O `TestClient` chama a API
real com o relógio `FrozenClock`. `_submit` abre um pedido de eliminação de um IP escolhido, e
cada teste apaga os pedidos e o usuário que criou. Precisa de PostgreSQL com pgvector local
(`migrated_database`); sem ele pula, e com `REQUIRE_INTEGRATION_DB=1` falha.
"""

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.adapters.password_hasher import get_password_hasher
from app.core.container import get_clock, get_settings
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.main import create_app
from app.models.data_subject_request import DataSubjectRequest
from app.prompts.privacy import RATE_LIMITED
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.users import UserRepository

pytestmark = pytest.mark.integration

ORIGIN = "http://localhost:5173"
HMAC_KEY = "test-hmac-key"
PASSWORD = "correct-horse-1"
FIXED = datetime(2026, 11, 3, 9, 30, tzinfo=UTC)


class FrozenClock:
    """Relógio parado em `FIXED`: `received_at` e `due_at` saem dele."""

    def now(self) -> datetime:
        return FIXED


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch, migrated_database: str) -> TestClient:
    """API real com o adaptador `fake` e o relógio parado."""
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", HMAC_KEY)
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_AI_ADAPTER", "fake")
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_clock] = FrozenClock
    return TestClient(application)


def test_a_request_from_the_channel_is_due_in_fifteen_days(
    api: TestClient, migrated_database: str
) -> None:
    ip = _ip()
    response = _submit(api, ip=ip, email="  Titular@Example.com ")
    created: list[UUID] = []
    try:
        assert response.status_code == 201, response.text
        body = response.json()
        created.append(UUID(body["id"]))
        assert body["status"] == "open"
        assert body["request_type"] == "deletion"
        row = _run(_row(migrated_database, UUID(body["id"])))
        assert row.contact_email == "titular@example.com"
        assert row.user_id is None
        assert row.received_at == FIXED
        assert row.due_at == FIXED + timedelta(days=15)
        assert row.closed_at is None
    finally:
        _run(_delete(migrated_database, created))


def test_the_sixth_request_from_the_same_ip_in_the_day_is_limited(
    api: TestClient, migrated_database: str
) -> None:
    ip = _ip()
    created: list[UUID] = []
    try:
        for _ in range(5):
            response = _submit(api, ip=ip)
            assert response.status_code == 201
            created.append(UUID(response.json()["id"]))
        limited = _submit(api, ip=ip)
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "rate_limited"
        assert limited.json()["error"]["message"] == RATE_LIMITED
        assert limited.json()["error"]["retry_after_seconds"] > 0
        other_ip = _submit(api, ip=_ip())
        assert other_ip.status_code == 201
        created.append(UUID(other_ip.json()["id"]))
    finally:
        _run(_delete(migrated_database, created))


def test_invalid_requests_return_field_errors_and_store_nothing(api: TestClient) -> None:
    response = api.post(
        "/v1/privacy/requests",
        headers={"Origin": ORIGIN, "X-Forwarded-For": _ip()},
        json={"contact_email": "nada", "request_type": "marketing", "description": " "},
    )
    assert response.status_code == 422
    assert set(response.json()["error"]["field_errors"]) == {
        "contact_email",
        "request_type",
        "description",
    }


def test_a_contact_email_with_mailto_headers_is_refused(api: TestClient) -> None:
    """O admin responde pelo contato: `?bcc=` ou `,` virariam cópia no cliente de e-mail."""
    for email in ("vitima@example.com?bcc=atacante%40evil.com", "vitima@example.com,a@evil.com"):
        response = _submit(api, ip=_ip(), email=email)
        assert response.status_code == 422, email
        assert set(response.json()["error"]["field_errors"]) == {"contact_email"}


def test_a_description_with_a_null_character_is_refused(api: TestClient) -> None:
    response = api.post(
        "/v1/privacy/requests",
        headers={"Origin": ORIGIN, "X-Forwarded-For": _ip()},
        json={
            "contact_email": "titular@example.com",
            "request_type": "deletion",
            "description": "Apaguem meus dados" + chr(0),
        },
    )
    assert response.status_code == 422
    assert set(response.json()["error"]["field_errors"]) == {"description"}


def test_a_signed_in_member_request_is_linked_and_survives_account_deletion(
    api: TestClient, migrated_database: str
) -> None:
    email = f"dsr-{uuid4().hex}@example.com"
    created: list[UUID] = []
    try:
        _run(_insert_member(migrated_database, email))
        login = api.post(
            "/v1/auth/login",
            headers={"Origin": ORIGIN, "X-Forwarded-For": _ip()},
            json={"email": email, "password": PASSWORD},
        )
        assert login.status_code == 200
        response = _submit(api, ip=_ip(), email=email)
        assert response.status_code == 201
        request_id = UUID(response.json()["id"])
        created.append(request_id)
        assert _run(_row(migrated_database, request_id)).user_id is not None
        assert api.delete("/v1/me", headers={"Origin": ORIGIN}).status_code == 204
        assert _run(_row(migrated_database, request_id)).user_id is None
    finally:
        _run(_delete(migrated_database, created))
        _run(_delete_email(migrated_database, email))


def test_the_channel_needs_the_origin(api: TestClient) -> None:
    response = api.post(
        "/v1/privacy/requests",
        json={"contact_email": "a@example.com", "request_type": "other", "description": "x"},
    )
    assert response.status_code == 403


def _submit(client: TestClient, *, ip: str, email: str = "titular@example.com") -> Any:
    """Abre um pedido de eliminação pelo canal, com o `Origin` certo e o IP `ip`."""
    return client.post(
        "/v1/privacy/requests",
        headers={"Origin": ORIGIN, "X-Forwarded-For": ip},
        json={
            "contact_email": email,
            "request_type": "deletion",
            "description": "Quero que apaguem meus dados.",
        },
    )


def _ip() -> str:
    """IP falso e único por chamada: cada teste ganha o próprio balde de limite."""
    return f"test-{uuid4().hex}"


def _run(coro: Coroutine[object, object, Any]) -> Any:
    """Roda a corrotina num loop novo e devolve o resultado."""
    return asyncio.run(coro)


async def _row(database_url: str, request_id: UUID) -> DataSubjectRequest:
    """O pedido gravado com este id."""
    async with open_session(database_url) as session:
        row = await session.scalar(
            select(DataSubjectRequest).where(DataSubjectRequest.id == request_id)
        )
    assert row is not None
    return row


async def _delete(database_url: str, ids: list[UUID]) -> None:
    """Apaga os pedidos criados pelo teste."""
    if not ids:
        return
    async with open_session(database_url) as session, UnitOfWork(session):
        await session.execute(delete(DataSubjectRequest).where(DataSubjectRequest.id.in_(ids)))


async def _insert_member(database_url: str, email: str) -> None:
    """Grava um membro com `PASSWORD` e o aceite vigente dos Termos."""
    from app.domain.legal import LEGAL_DOCUMENT_VERSION
    from app.domain.registration import ConsentGrant, Purpose
    from app.repositories.consents import ConsentRepository

    async with open_session(database_url) as session, UnitOfWork(session):
        user_id = await UserRepository(session).insert(
            email=email,
            password_hash=get_password_hasher().hash_password(PASSWORD),
            full_name="Titular Teste",
            role="member",
            now=FIXED,
        )
        await ConsentRepository(session).insert_grants(
            user_id=user_id,
            grants=(ConsentGrant(Purpose.TERMS.value, LEGAL_DOCUMENT_VERSION),),
            source="form",
            granted_at=FIXED,
        )


async def _delete_email(database_url: str, email: str) -> None:
    """Apaga o usuário pelo e-mail, com as sessões e a auditoria dele."""
    from app.models.audit_event import AuditEvent

    async with open_session(database_url) as session, UnitOfWork(session):
        users = UserRepository(session)
        user = await users.get_by_email(email)
        if user is None:
            return
        await AuthSessionRepository(session).delete_for_user(user.id)
        await session.execute(delete(AuditEvent).where(AuditEvent.actor_user_id == user.id))
        await users.delete_user(user.id)
