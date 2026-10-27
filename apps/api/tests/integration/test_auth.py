"""Login, sessão, limite e autorização contra o PostgreSQL. Seções 10.3 a 10.5."""

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

from app.adapters.password_hasher import get_password_hasher
from app.core.container import get_clock, get_settings
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import LOGIN_IP_WINDOW, bucket_key, fixed_window_start, hash_session_secret
from app.main import create_app
from app.models.audit_event import AuditEvent
from app.models.rate_limit_window import RateLimitWindow
from app.prompts.auth import FORBIDDEN, INVALID_CREDENTIALS, UNAUTHENTICATED
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.users import UserRepository

pytestmark = pytest.mark.integration

ORIGIN = "http://localhost:5173"
HMAC_KEY = "test-hmac-key"
PASSWORD = "correct-horse-1"
WRONG_PASSWORD = "wrong-password-1"
FIXED = datetime(2026, 10, 27, 12, 7, tzinfo=UTC)


class FrozenClock:
    def now(self) -> datetime:
        return FIXED


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch, migrated_database: str) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", HMAC_KEY)
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "local")
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_clock] = FrozenClock
    return TestClient(application)


def test_wrong_login_uses_the_same_message_for_known_and_unknown_email(
    api: TestClient,
    migrated_database: str,
) -> None:
    email = _email("known")
    try:
        _run(_insert_user(migrated_database, email=email, role="member"))
        known = _login(api, email, WRONG_PASSWORD)
        unknown = _login(api, _email("missing"), WRONG_PASSWORD)
    finally:
        _run(_delete_email(migrated_database, email))
    assert known.status_code == unknown.status_code == 401
    assert known.json()["error"]["message"] == INVALID_CREDENTIALS
    assert unknown.json()["error"]["message"] == INVALID_CREDENTIALS
    assert known.json()["error"]["code"] == unknown.json()["error"]["code"] == "unauthenticated"


def test_login_sets_a_host_only_cookie_and_stores_only_hashes(
    api: TestClient,
    migrated_database: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    email = _email("session")
    try:
        _run(_insert_user(migrated_database, email=email, role="member"))
        response = _login(api, email, PASSWORD)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        attrs = _cookie_attributes(response)
        assert "httponly" in attrs
        assert attrs["samesite"] == "lax"
        assert attrs["max-age"] == "1209600"
        assert "domain" not in attrs
        assert "secure" not in attrs
        secret = _cookie_value(response)
        body = response.json()
        assert body["email"] == email
        assert body["role"] == "member"
        assert body["needs_legal_acceptance"] is True
        assert "password" not in body
        assert "password_hash" not in body
        _run(_assert_hashes(migrated_database, email=email, password=PASSWORD, secret=secret))
        me = api.get("/v1/me", headers={"cookie": f"atrium_session={secret}"})
        assert me.status_code == 200
        assert me.headers["cache-control"] == "no-store"
    finally:
        _run(_delete_email(migrated_database, email))
    output = capsys.readouterr().out
    assert email not in output
    assert PASSWORD not in output


def test_logout_revokes_the_session(api: TestClient, migrated_database: str) -> None:
    email = _email("logout")
    try:
        _run(_insert_user(migrated_database, email=email, role="member"))
        logged_in = _login(api, email, PASSWORD)
        secret = _cookie_value(logged_in)
        cookie = {"cookie": f"atrium_session={secret}"}
        logged_out = api.post("/v1/auth/logout", headers={**cookie, "Origin": ORIGIN})
        assert logged_out.status_code == 204
        assert logged_out.headers["cache-control"] == "no-store"
        again = api.get("/v1/me", headers=cookie)
        assert again.status_code == 401
        assert again.json()["error"]["message"] == UNAUTHENTICATED
        _run(_assert_revoked(migrated_database, secret))
    finally:
        _run(_delete_email(migrated_database, email))


def test_login_above_the_email_limit_keeps_the_same_message(
    api: TestClient,
    migrated_database: str,
) -> None:
    known = _email("limited-known")
    unknown = _email("limited-unknown")
    try:
        _run(_insert_user(migrated_database, email=known, role="member"))
        known_last = _exhaust_email(api, known)
        unknown_last = _exhaust_email(api, unknown)
    finally:
        _run(_delete_email(migrated_database, known))
    assert known_last.status_code == unknown_last.status_code == 429
    assert known_last.json()["error"]["message"] == INVALID_CREDENTIALS
    assert unknown_last.json()["error"]["message"] == INVALID_CREDENTIALS
    assert known_last.json()["error"]["retry_after_seconds"] == 480
    assert known_last.headers["cache-control"] == "no-store"


def test_login_above_the_ip_limit_returns_429(api: TestClient, migrated_database: str) -> None:
    email = _email("ip-limit")
    ip = _ip()
    start = fixed_window_start(FIXED, LOGIN_IP_WINDOW)
    key = bucket_key(purpose="login_ip", subject=ip, day=FIXED.date(), key=HMAC_KEY)
    try:
        _run(_insert_user(migrated_database, email=email, role="member"))
        _run(_seed_window(migrated_database, key=key, start=start, count=30))
        response = _login(api, email, WRONG_PASSWORD, ip=ip)
    finally:
        _run(_delete_email(migrated_database, email))
    assert response.status_code == 429
    assert response.json()["error"]["message"] == INVALID_CREDENTIALS
    assert response.json()["error"]["retry_after_seconds"] == 3180


def test_member_cannot_call_an_admin_route(api: TestClient, migrated_database: str) -> None:
    member = _email("member")
    admin = _email("admin")
    try:
        _run(_insert_user(migrated_database, email=member, role="member"))
        _run(_insert_user(migrated_database, email=admin, role="admin"))
        member_cookie = _cookie_value(_login(api, member, PASSWORD))
        admin_cookie = _cookie_value(_login(api, admin, PASSWORD))
        refused = api.get(
            "/v1/admin/probe",
            headers={"cookie": f"atrium_session={member_cookie}"},
        )
        allowed = api.get(
            "/v1/admin/probe",
            headers={"cookie": f"atrium_session={admin_cookie}"},
        )
        api.cookies.clear()
        missing = api.get("/v1/admin/probe")
    finally:
        _run(_delete_email(migrated_database, member))
        _run(_delete_email(migrated_database, admin))
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "forbidden"
    assert refused.json()["error"]["message"] == FORBIDDEN
    assert allowed.status_code == 200
    assert allowed.json() == {"status": "ok"}
    assert missing.status_code == 401


def test_production_cookie_is_secure(
    monkeypatch: pytest.MonkeyPatch,
    migrated_database: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", HMAC_KEY)
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_clock] = FrozenClock
    email = _email("secure")
    try:
        _run(_insert_user(migrated_database, email=email, role="member"))
        response = _login(TestClient(application), email, PASSWORD)
    finally:
        _run(_delete_email(migrated_database, email))
        get_settings.cache_clear()
    assert "secure" in _cookie_attributes(response)


def _login(
    client: TestClient,
    email: str,
    password: str,
    *,
    ip: str | None = None,
) -> Any:
    return client.post(
        "/v1/auth/login",
        headers={
            "Origin": ORIGIN,
            "X-Forwarded-For": ip or _ip(),
            "User-Agent": "pytest",
        },
        json={"email": email, "password": password},
    )


def _exhaust_email(client: TestClient, email: str) -> Any:
    ip = _ip()
    response: Any = None
    for attempt in range(1, 12):
        response = _login(client, email, WRONG_PASSWORD, ip=ip)
        if attempt < 11:
            assert response.status_code == 401
            assert response.json()["error"]["message"] == INVALID_CREDENTIALS
    assert response is not None
    return response


def _cookie_value(response: Any) -> str:
    header = response.headers["set-cookie"]
    if not isinstance(header, str):
        raise AssertionError(header)
    return header.split(";", 1)[0].split("=", 1)[1]


def _cookie_attributes(response: Any) -> dict[str, str]:
    header = response.headers["set-cookie"]
    if not isinstance(header, str):
        raise AssertionError(header)
    attributes: dict[str, str] = {}
    for part in header.split(";")[1:]:
        name, separator, value = part.strip().partition("=")
        attributes[name.lower()] = value if separator else ""
    return attributes


def _email(label: str) -> str:
    return f"{label}-{uuid4().hex}@example.com"


def _ip() -> str:
    return f"test-{uuid4().hex}"


def _run(coro: Coroutine[object, object, None]) -> None:
    asyncio.run(coro)


async def _insert_user(database_url: str, *, email: str, role: str) -> None:
    async with open_session(database_url) as session, UnitOfWork(session):
        await UserRepository(session).insert(
            email=email,
            password_hash=get_password_hasher().hash_password(PASSWORD),
            full_name="Visitante Teste",
            role=role,
            now=datetime.now(UTC),
        )


async def _delete_email(database_url: str, email: str) -> None:
    async with open_session(database_url) as session, UnitOfWork(session):
        users = UserRepository(session)
        user = await users.get_by_email(email)
        if user is None:
            return
        await AuthSessionRepository(session).delete_for_user(user.id)
        await session.execute(delete(AuditEvent).where(AuditEvent.actor_user_id == user.id))
        await users.delete_user(user.id)


async def _seed_window(database_url: str, *, key: str, start: datetime, count: int) -> None:
    async with open_session(database_url) as session, UnitOfWork(session):
        session.add(RateLimitWindow(bucket_key=key, window_start=start, count=count))


async def _assert_hashes(database_url: str, *, email: str, password: str, secret: str) -> None:
    async with open_session(database_url) as session:
        stored_password = await session.scalar(
            text("SELECT password_hash FROM users WHERE email = :email"),
            {"email": email},
        )
        stored_token = await session.scalar(
            text(
                "SELECT token_hash FROM auth_sessions "
                "JOIN users ON users.id = auth_sessions.user_id "
                "WHERE users.email = :email"
            ),
            {"email": email},
        )
    assert isinstance(stored_password, str)
    assert stored_password != password
    assert stored_password.startswith("$argon2id$")
    assert isinstance(stored_token, str)
    assert stored_token == hash_session_secret(secret)
    assert secret not in stored_token


async def _assert_revoked(database_url: str, secret: str) -> None:
    async with open_session(database_url) as session:
        revoked_at = await session.scalar(
            text("SELECT revoked_at FROM auth_sessions WHERE token_hash = :token_hash"),
            {"token_hash": hash_session_secret(secret)},
        )
    assert revoked_at is not None
