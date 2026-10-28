"""Login, logout e sessão. A transação do limite fecha antes do argon2. Seção 6.4."""

from dataclasses import dataclass
from datetime import UTC, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.session_secret import new_session_secret
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.auth import (
    LOGIN_EMAIL_WINDOW,
    LOGIN_IP_WINDOW,
    SESSION_MAX_AGE_SECONDS,
    SessionCookie,
    bucket_key,
    clean_user_agent,
    email_is_valid,
    fixed_window_start,
    hash_session_secret,
    login_rate_decision,
    normalize_email,
    password_is_checkable,
    password_length_is_valid,
    session_cookie,
)
from app.domain.errors import (
    Conflict,
    Forbidden,
    NotFound,
    RateLimited,
    Unauthenticated,
    ValidationFailed,
)
from app.domain.legal import LEGAL_DOCUMENT_VERSION, needs_legal_acceptance
from app.domain.profile import Profile
from app.models.user import User
from app.ports.clock import Clock
from app.ports.password_hasher import PasswordHasher
from app.prompts.auth import (
    ADMIN_CREDENTIALS_MISSING,
    ADMIN_DISPLAY_NAME,
    ADMIN_EMAIL_INVALID,
    ADMIN_LAST,
    ADMIN_NOT_FOUND,
    ADMIN_PASSWORD_LENGTH,
    FORBIDDEN,
    INVALID_CREDENTIALS,
    UNAUTHENTICATED,
)
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.bootstrap import BootstrapRepository
from app.repositories.consents import ConsentRepository
from app.repositories.rate_limits import RateLimitRepository
from app.repositories.users import UserRepository


@dataclass(frozen=True, slots=True)
class LoginResult:
    profile: Profile
    cookie: SessionCookie


@dataclass(frozen=True, slots=True)
class _UserRecord:
    id: UUID
    email: str
    full_name: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None
    role: str
    password_hash: str
    terms_version: str | None


class AuthService:
    def __init__(
        self,
        *,
        database_url: str,
        clock: Clock,
        hasher: PasswordHasher,
        hmac_key: str,
        app_env: str,
    ) -> None:
        self._database_url = database_url
        self._clock = clock
        self._hasher = hasher
        self._hmac_key = hmac_key
        self._app_env = app_env

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str,
        client_ip: str,
    ) -> LoginResult:
        if not self._hmac_key:
            raise RuntimeError("RATE_LIMIT_HMAC_KEY vazio.")
        now = self._clock.now()
        normalized = normalize_email(email)
        day = now.astimezone(UTC).date()
        email_key = bucket_key(
            purpose="login_email",
            subject=normalized,
            day=day,
            key=self._hmac_key,
        )
        ip_key = bucket_key(purpose="login_ip", subject=client_ip, day=day, key=self._hmac_key)
        email_window = fixed_window_start(now, LOGIN_EMAIL_WINDOW)
        ip_window = fixed_window_start(now, LOGIN_IP_WINDOW)

        async with open_session(self._database_url) as session, UnitOfWork(session):
            rates = RateLimitRepository(session)
            email_count = await rates.increment(email_key, email_window)
            ip_count = await rates.increment(ip_key, ip_window)
            decision = login_rate_decision(
                email_count=email_count,
                ip_count=ip_count,
                now=now,
                email_window_start=email_window,
                ip_window_start=ip_window,
            )
            record: _UserRecord | None = None
            if not decision.limited:
                user = await UserRepository(session).get_by_email(normalized)
                if user is not None:
                    record = _record(user, await _terms_version(session, user.id))

        if decision.limited:
            raise RateLimited(
                INVALID_CREDENTIALS,
                retry_after_seconds=decision.retry_after_seconds,
            )
        if not self._password_matches(password, None if record is None else record.password_hash):
            raise Unauthenticated(INVALID_CREDENTIALS)
        if record is None:
            raise Unauthenticated(INVALID_CREDENTIALS)

        secret = new_session_secret()
        expires_at = now + timedelta(seconds=SESSION_MAX_AGE_SECONDS)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await AuthSessionRepository(session).create(
                token_hash=hash_session_secret(secret),
                user_id=record.id,
                expires_at=expires_at,
                user_agent=clean_user_agent(user_agent),
            )
            await UserRepository(session).touch(record.id, now)
        return LoginResult(
            profile=_profile(record),
            cookie=session_cookie(secret=secret, app_env=self._app_env),
        )

    async def authenticate(self, secret: str | None) -> Profile:
        record = await self._active_user(secret)
        if record is None:
            raise Unauthenticated(UNAUTHENTICATED)
        return _profile(record)

    async def require_admin(self, secret: str | None) -> Profile:
        profile = await self.authenticate(secret)
        if profile.role != "admin":
            raise Forbidden(FORBIDDEN)
        return profile

    async def logout(self, secret: str | None) -> None:
        if not secret:
            raise Unauthenticated(UNAUTHENTICATED)
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            revoked = await AuthSessionRepository(session).revoke(hash_session_secret(secret), now)
        if not revoked:
            raise Unauthenticated(UNAUTHENTICATED)

    def _password_matches(self, password: str, stored_hash: str | None) -> bool:
        if not password_is_checkable(password):
            return False
        if stored_hash is None:
            self._hasher.verify_password(password, self._hasher.dummy_hash)
            return False
        return self._hasher.verify_password(password, stored_hash)

    async def _active_user(self, secret: str | None) -> _UserRecord | None:
        if not secret:
            return None
        now = self._clock.now()
        record: _UserRecord | None = None
        async with open_session(self._database_url) as session, UnitOfWork(session):
            sessions = AuthSessionRepository(session)
            found = await sessions.get_active(hash_session_secret(secret), now)
            if found is not None:
                user = await UserRepository(session).get_by_id(found.user_id)
                if user is not None:
                    record = _record(user, await _terms_version(session, user.id))
        return record


class BootstrapAdminService:
    def __init__(self, *, database_url: str, clock: Clock, hasher: PasswordHasher) -> None:
        self._database_url = database_url
        self._clock = clock
        self._hasher = hasher

    async def ensure(self, *, email: str, password: str) -> bool:
        """Cria o admin só quando nenhum existe. Devolve True se criou."""
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await BootstrapRepository(session).lock()
            users = UserRepository(session)
            if await users.count_by_role("admin") > 0:
                return False
            _require_admin_credentials(email, password)
            await users.insert(
                email=normalize_email(email),
                password_hash=self._hasher.hash_password(password),
                full_name=ADMIN_DISPLAY_NAME,
                role="admin",
                now=self._clock.now(),
            )
        return True

    async def remove(self, email: str) -> None:
        normalized = normalize_email(email)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await BootstrapRepository(session).lock()
            users = UserRepository(session)
            user = await users.get_by_email(normalized)
            if user is None or user.role != "admin":
                raise NotFound(ADMIN_NOT_FOUND)
            if await users.count_by_role("admin") <= 1:
                raise Conflict(ADMIN_LAST)
            await AuthSessionRepository(session).delete_for_user(user.id)
            await users.delete_user(user.id)


def _require_admin_credentials(email: str, password: str) -> None:
    if not email.strip() or not password:
        raise ValidationFailed(ADMIN_CREDENTIALS_MISSING)
    if not email_is_valid(normalize_email(email)):
        raise ValidationFailed(ADMIN_EMAIL_INVALID)
    if not password_length_is_valid(password):
        raise ValidationFailed(ADMIN_PASSWORD_LENGTH)


async def _terms_version(session: AsyncSession, user_id: UUID) -> str | None:
    current = await ConsentRepository(session).has_current_terms(user_id, LEGAL_DOCUMENT_VERSION)
    if current:
        return LEGAL_DOCUMENT_VERSION
    return None


def _record(user: User, terms_version: str | None) -> _UserRecord:
    return _UserRecord(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        visitor_type=user.visitor_type,
        visit_reason=user.visit_reason,
        role=user.role,
        password_hash=user.password_hash,
        terms_version=terms_version,
    )


def _profile(record: _UserRecord) -> Profile:
    return Profile(
        id=record.id,
        email=record.email,
        full_name=record.full_name,
        phone=record.phone,
        visitor_type=record.visitor_type,
        visit_reason=record.visit_reason,
        role=record.role,
        needs_legal_acceptance=needs_legal_acceptance(record.terms_version),
    )

