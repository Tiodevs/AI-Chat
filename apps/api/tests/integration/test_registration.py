"""API de cadastro contra o PostgreSQL. Seções 7.2, 8.1, 8.5 e 10.4."""

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.adapters.fake_chat import FakeChatProvider
from app.core.container import get_clock, get_registration_service, get_settings
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import bucket_key
from app.domain.legal import LEGAL_DOCUMENT_VERSION
from app.domain.registration import REGISTRATION_IP_PURPOSE, registration_window_start
from app.main import create_app
from app.models.consent_record import ConsentRecord
from app.models.rate_limit_window import RateLimitWindow
from app.models.registration_session import RegistrationSession
from app.models.user import User
from app.ports.chat import ToolResult
from app.prompts.registration import EMAIL_TAKEN, prompt_for
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.users import UserRepository
from app.services.registration import RegistrationService
from app.workflows.registration import RegistrationWorkflow

pytestmark = pytest.mark.integration

ORIGIN = "http://localhost:5173"
HMAC_KEY = "test-hmac-key"
PASSWORD = "correct-horse-1"
SECRET_PASSWORD = "senha-que-nao-pode-vazar"
FIXED = datetime(2026, 10, 28, 3, 0, tzinfo=UTC)


class FrozenClock:
    def now(self) -> datetime:
        return FIXED


@pytest.fixture
def chat() -> FakeChatProvider:
    return FakeChatProvider()


@pytest.fixture
def api(
    monkeypatch: pytest.MonkeyPatch,
    migrated_database: str,
    chat: FakeChatProvider,
) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    monkeypatch.setenv("RATE_LIMIT_HMAC_KEY", HMAC_KEY)
    monkeypatch.setenv("WEB_ORIGIN", ORIGIN)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_AI_ADAPTER", "fake")
    get_settings.cache_clear()
    application = create_app()
    application.dependency_overrides[get_clock] = FrozenClock
    application.dependency_overrides[get_registration_service] = lambda: RegistrationService(
        database_url=migrated_database,
        clock=FrozenClock(),
        hasher=_hasher(),
        hmac_key=HMAC_KEY,
        app_env="local",
        workflow=RegistrationWorkflow(chat),
    )
    return TestClient(application)


def test_registration_password_endpoint_logs_omit_the_password(
    api: TestClient,
    chat: FakeChatProvider,
    migrated_database: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_id = _start(api)
    try:
        _collect_required(api, chat, session_id, _email("logs"))
        _skip_optionals(api, chat, session_id)
        response = api.post(
            f"/v1/registration/sessions/{session_id}/password",
            headers=_headers(),
            json={"password": SECRET_PASSWORD},
        )
        assert response.status_code == 200
        assert SECRET_PASSWORD not in response.text
        transcript, stored_hash, status = _run(_session_secret(migrated_database, session_id))
    finally:
        _run(_cleanup(migrated_database, [], [session_id]))
    rendered = " ".join(str(item) for item in transcript)
    assert SECRET_PASSWORD not in rendered
    assert "password" not in rendered
    assert stored_hash is not None
    assert stored_hash != SECRET_PASSWORD
    assert stored_hash.startswith("$argon2id$")
    assert status == "awaiting_review"
    output = capsys.readouterr().out + capsys.readouterr().err
    assert SECRET_PASSWORD not in output


def test_registration_completion_without_terms_or_age_creates_no_user(
    api: TestClient,
    chat: FakeChatProvider,
    migrated_database: str,
) -> None:
    email = _email("terms")
    session_id = _prepare_acceptance(api, chat, email)
    try:
        missing_terms = _accept(api, session_id, accept_terms=False, age_18_plus=True)
        missing_age = _accept(api, session_id, accept_terms=True, age_18_plus=False)
        assert missing_terms.status_code == missing_age.status_code == 422
        assert _run(_count_users(migrated_database, email)) == 0
        created = _accept(api, session_id, accept_terms=True, age_18_plus=True)
        assert created.status_code == 200
        assert created.json()["role"] == "member"
        assert _run(_count_users(migrated_database, email)) == 1
    finally:
        _run(_cleanup(migrated_database, [email], [session_id]))


def test_registration_discards_sensitive_fields_without_personalization(
    api: TestClient,
    migrated_database: str,
) -> None:
    email = _email("sensitive")
    try:
        response = _submit(
            api,
            email,
            visitor_type="patient",
            visit_reason="own_appointment",
            personalization=False,
        )
        assert response.status_code == 200
        assert response.json()["visitor_type"] is None
        assert response.json()["visit_reason"] is None
        user, grants = _run(_stored(migrated_database, email))
        assert user.visitor_type is None
        assert user.visit_reason is None
        assert user.role == "member"
        assert "profile_personalization" not in {grant.purpose for grant in grants}
        again = _submit(
            api,
            email,
            visitor_type="patient",
            visit_reason="own_appointment",
            personalization=False,
        )
        assert again.status_code == 409
        assert again.json()["error"]["field_errors"]["email"] == EMAIL_TAKEN
        assert _run(_count_users(migrated_database, email)) == 1
    finally:
        _run(_cleanup(migrated_database, [email], []))


def test_registration_chat_and_form_create_the_same_consents(
    api: TestClient,
    chat: FakeChatProvider,
    migrated_database: str,
) -> None:
    chat_email = _email("chat")
    form_email = _email("form")
    session_id = _start(api)
    try:
        _collect_required(api, chat, session_id, chat_email)
        _say(api, chat, session_id, "telefone", {"phone": "5550142600"})
        _say(api, chat, session_id, "tipo", {"visitor_type": "visitor"})
        _say(api, chat, session_id, "motivo", {"visit_reason": "visiting_someone"})
        _password_and_review(api, session_id)
        accepted = _accept(
            api,
            session_id,
            accept_terms=True,
            age_18_plus=True,
            personalization=True,
            quality=True,
        )
        assert accepted.status_code == 200
        assert accepted.json()["needs_legal_acceptance"] is False
        me = api.get("/v1/me", headers={"cookie": f"atrium_session={_cookie(accepted)}"})
        assert me.status_code == 200
        assert me.json()["needs_legal_acceptance"] is False
        submitted = _submit(
            api,
            form_email,
            visitor_type="visitor",
            visit_reason="visiting_someone",
            personalization=True,
            quality=True,
            phone="5550142600",
        )
        assert submitted.status_code == 200
        assert submitted.json()["role"] == "member"
        _chat_user, chat_grants = _run(_stored(migrated_database, chat_email))
        form_user, form_grants = _run(_stored(migrated_database, form_email))
        assert _chat_user.role == form_user.role == "member"
        assert _chat_user.visitor_type == form_user.visitor_type == "visitor"
        assert form_user.visit_reason == "visiting_someone"
        assert _grant_key(chat_grants) == _grant_key(form_grants)
        assert {grant.source for grant in chat_grants} == {"chat"}
        assert {grant.source for grant in form_grants} == {"form"}
    finally:
        _run(_cleanup(migrated_database, [chat_email, form_email], [session_id]))


def test_registration_second_acceptance_does_not_create_another_user(
    api: TestClient,
    chat: FakeChatProvider,
    migrated_database: str,
) -> None:
    email = _email("twice")
    session_id = _prepare_acceptance(api, chat, email)
    try:
        first = _accept(api, session_id, accept_terms=True, age_18_plus=True)
        second = _accept(api, session_id, accept_terms=True, age_18_plus=True)
        assert first.status_code == second.status_code == 200
        assert first.json()["id"] == second.json()["id"]
        assert _run(_count_users(migrated_database, email)) == 1
        _user, grants = _run(_stored(migrated_database, email))
        assert len(grants) == 2
        transcript, stored_hash, status = _run(_session_secret(migrated_database, session_id))
        assert status == "completed"
        assert transcript == []
        assert stored_hash is None
    finally:
        _run(_cleanup(migrated_database, [email], [session_id]))


def test_registration_guest_conversation_belongs_to_the_member(
    api: TestClient,
    migrated_database: str,
) -> None:
    email = _email("guest")
    created = api.post("/v1/conversations", headers=_headers())
    assert created.status_code == 201
    guest = created.cookies.get("atrium_guest")
    assert isinstance(guest, str) and guest
    conversation_id = created.json()["id"]
    api.cookies.clear()
    try:
        registered = api.post(
            "/v1/registration/form",
            headers={**_headers(), "cookie": f"atrium_guest={guest}"},
            json=_form(email),
        )
        assert registered.status_code == 200
        api.cookies.clear()
        listed = api.get(
            "/v1/conversations",
            headers={"cookie": f"atrium_session={_cookie(registered)}"},
        )
        assert listed.status_code == 200
        assert conversation_id in {item["id"] for item in listed.json()["conversations"]}
    finally:
        _run(_cleanup(migrated_database, [email], []))


def test_registration_duplicate_email_is_a_field_error(
    api: TestClient,
    chat: FakeChatProvider,
    migrated_database: str,
) -> None:
    taken = _email("taken")
    free = _email("free")
    _run(_insert_user(migrated_database, taken))
    session_id = _start(api)
    try:
        _say(api, chat, session_id, "nome", {"full_name": "Ana Costa"})
        stored = _say(api, chat, session_id, "email", {"email": free})
        assert stored.json()["fields"]["email"] == free
        rejected = _say(api, chat, session_id, "outro", {"email": taken})
        assert rejected.json()["fields"]["email"] == free
        assert rejected.json()["field_errors"]["email"] == EMAIL_TAKEN
        assert _run(_count_users(migrated_database, taken)) == 1
    finally:
        _run(_cleanup(migrated_database, [taken, free], [session_id]))


def test_registration_rate_limit_returns_429(
    api: TestClient,
    migrated_database: str,
) -> None:
    session_id = _start(api)
    ip = f"test-{uuid4().hex}"
    start = registration_window_start(FIXED)
    key = bucket_key(
        purpose=REGISTRATION_IP_PURPOSE,
        subject=ip,
        day=FIXED.date(),
        key=HMAC_KEY,
    )
    try:
        _run(_seed_window(migrated_database, key=key, start=start, count=20))
        response = api.post(
            f"/v1/registration/sessions/{session_id}/messages",
            headers=_headers(ip),
            json={"text": "Ana Costa"},
        )
    finally:
        _run(_cleanup(migrated_database, [], [session_id]))
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert response.json()["error"]["retry_after_seconds"] == 3600


def _prepare_acceptance(api: TestClient, chat: FakeChatProvider, email: str) -> str:
    session_id = _start(api)
    _collect_required(api, chat, session_id, email)
    _skip_optionals(api, chat, session_id)
    _password_and_review(api, session_id)
    return session_id


def _start(api: TestClient) -> str:
    response = api.post("/v1/registration/sessions", headers=_headers())
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["next_step"] == "full_name"
    assert body["messages"][0]["text"]
    assert "password" not in body["messages"][0]
    return str(body["id"])


def _collect_required(api: TestClient, chat: FakeChatProvider, session_id: str, email: str) -> None:
    named = _say(api, chat, session_id, "Ana Costa", {"full_name": "Ana Costa"})
    assert named.json()["next_step"] == "email"
    assert named.json()["prompt"] == prompt_for("email", correcting=False)
    mailed = _say(api, chat, session_id, email, {"email": email})
    assert mailed.json()["fields"]["email"] == email
    assert mailed.json()["next_step"] == "phone"


def _skip_optionals(api: TestClient, chat: FakeChatProvider, session_id: str) -> None:
    for expected in ("visitor_type", "visit_reason", "password"):
        response = _say(api, chat, session_id, "pular", {"skip_current": True})
        assert response.json()["next_step"] == expected


def _password_and_review(api: TestClient, session_id: str) -> None:
    password = api.post(
        f"/v1/registration/sessions/{session_id}/password",
        headers=_headers(),
        json={"password": PASSWORD},
    )
    assert password.status_code == 200, password.text
    assert password.json()["next_step"] == "review"
    review = api.post(
        f"/v1/registration/sessions/{session_id}/review",
        headers=_headers(),
        json={"accept": True},
    )
    assert review.status_code == 200, review.text
    assert review.json()["next_step"] == "acceptance"


def _say(
    api: TestClient,
    chat: FakeChatProvider,
    session_id: str,
    text: str,
    arguments: dict[str, object],
) -> Any:
    chat.script(tool_result=ToolResult(name="set_fields", arguments=arguments))
    response = api.post(
        f"/v1/registration/sessions/{session_id}/messages",
        headers=_headers(),
        json={"text": text},
    )
    assert response.status_code == 200, response.text
    return response


def _accept(
    api: TestClient,
    session_id: str,
    *,
    accept_terms: bool,
    age_18_plus: bool,
    personalization: bool = False,
    quality: bool = False,
) -> Any:
    return api.post(
        f"/v1/registration/sessions/{session_id}/acceptance",
        headers=_headers(),
        json={
            "accept_terms": accept_terms,
            "document_version": LEGAL_DOCUMENT_VERSION,
            "age_18_plus": age_18_plus,
            "profile_personalization": personalization,
            "quality_improvement": quality,
        },
    )


def _submit(
    api: TestClient,
    email: str,
    *,
    visitor_type: str | None = None,
    visit_reason: str | None = None,
    personalization: bool = False,
    quality: bool = False,
    phone: str | None = None,
) -> Any:
    return api.post("/v1/registration/form", headers=_headers(), json=_form(
        email,
        visitor_type=visitor_type,
        visit_reason=visit_reason,
        personalization=personalization,
        quality=quality,
        phone=phone,
    ))


def _form(
    email: str,
    *,
    visitor_type: str | None = None,
    visit_reason: str | None = None,
    personalization: bool = False,
    quality: bool = False,
    phone: str | None = None,
) -> dict[str, object]:
    return {
        "full_name": "Ana Costa",
        "email": email,
        "phone": phone,
        "visitor_type": visitor_type,
        "visit_reason": visit_reason,
        "password": PASSWORD,
        "accept_terms": True,
        "document_version": LEGAL_DOCUMENT_VERSION,
        "age_18_plus": True,
        "profile_personalization": personalization,
        "quality_improvement": quality,
    }


def _headers(ip: str | None = None) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-Forwarded-For": ip or f"test-{uuid4().hex}"}


def _cookie(response: Any) -> str:
    header = response.headers["set-cookie"]
    if not isinstance(header, str):
        raise AssertionError(header)
    return header.split(";", 1)[0].split("=", 1)[1]


def _email(label: str) -> str:
    return f"{label}-{uuid4().hex}@example.com"


def _grant_key(grants: list[ConsentRecord]) -> set[tuple[str, str]]:
    return {(grant.purpose, grant.document_version) for grant in grants}


def _hasher() -> Any:
    from app.adapters.password_hasher import get_password_hasher

    return get_password_hasher()


def _run[T](coro: Coroutine[object, object, T]) -> T:
    return asyncio.run(coro)


async def _insert_user(database_url: str, email: str) -> None:
    async with open_session(database_url) as session, UnitOfWork(session):
        await UserRepository(session).insert(
            email=email,
            password_hash="hash",
            full_name="Visitante Teste",
            role="member",
            now=FIXED,
        )


async def _seed_window(database_url: str, *, key: str, start: datetime, count: int) -> None:
    async with open_session(database_url) as session, UnitOfWork(session):
        session.add(RateLimitWindow(bucket_key=key, window_start=start, count=count))


async def _count_users(database_url: str, email: str) -> int:
    async with open_session(database_url) as session:
        value = await session.scalar(
            select(func.count()).select_from(User).where(User.email == email)
        )
    return int(value or 0)


async def _stored(
    database_url: str,
    email: str,
) -> tuple[User, list[ConsentRecord]]:
    async with open_session(database_url) as session:
        user = await session.scalar(select(User).where(User.email == email))
        if user is None:
            raise AssertionError(email)
        grants = list(
            await session.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user.id))
        )
        return user, grants


async def _session_secret(
    database_url: str,
    session_id: str,
) -> tuple[list[Any], str | None, str]:
    async with open_session(database_url) as session:
        row = await session.get(RegistrationSession, UUID(session_id))
        if row is None:
            raise AssertionError(session_id)
        return list(row.transcript), row.password_hash, row.status


async def _cleanup(database_url: str, emails: list[str], session_ids: list[str]) -> None:
    async with open_session(database_url) as session, UnitOfWork(session):
        users = UserRepository(session)
        for email in emails:
            user = await users.get_by_email(email)
            if user is None:
                continue
            await AuthSessionRepository(session).delete_for_user(user.id)
            await users.delete_user(user.id)
        if session_ids:
            await session.execute(
                delete(RegistrationSession).where(
                    RegistrationSession.id.in_([UUID(item) for item in session_ids])
                )
            )
