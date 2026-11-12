"""Login, logout e sessão. A transação do limite fecha antes do argon2. Seção 6.4.

Camada de serviço, com dois serviços:

- `AuthService`: login, logout e a leitura da sessão. Os controladores o montam por pedido:
  `controllers/auth.py` (login, logout e `GET /v1/me`), `controllers/account.py` e
  `controllers/privacy.py` (`authenticate`), e `controllers/admin_guard.py` e
  `controllers/admin_probe.py` (`require_admin`), que protegem as rotas de admin antes de
  chamar o serviço delas.
- `BootstrapAdminService`: cria o primeiro admin ou remove um. Só o script
  `scripts/bootstrap_admin.py` o usa, no pré-deploy (seção 10.5).

Usa `AuthSessionRepository`, `UserRepository`, `ConsentRepository`, `RateLimitRepository`
e `BootstrapRepository`, as regras de `domain/auth.py` e a porta `PasswordHasher` (argon2id,
`adapters/password_hasher.py`). Sessão e cookie seguem as seções 8.1 e 10.3; os baldes de
login, a seção 10.4.

O argon2 roda no loop de eventos, fora de transação. A Etapa 13.1 o leva para
`asyncio.to_thread`.
"""

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
    session_max_age_seconds,
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
    """O perfil de `GET /v1/me` e o cookie `atrium_session` que o controlador define."""

    profile: Profile
    cookie: SessionCookie


@dataclass(frozen=True, slots=True)
class _UserRecord:
    """Cópia da linha do usuário feita dentro da transação.

    `password_hash` só serve à conferência do login e nunca sai do serviço: `Profile` não
    tem hash. `terms_version` é a versão vigente quando há aceite dela, e `None` quando o
    membro precisa aceitar os documentos de novo.
    """

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
    """Sessões de autenticação: criar no login, ler, exigir admin e revogar.

    `hmac_key` é a `RATE_LIMIT_HMAC_KEY` dos baldes de login. `app_env` decide o atributo
    `Secure` do cookie, ligado fora de `local`.
    """

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
        """Confere e-mail e senha e abre uma sessão de 14 dias, ou de 12 horas para a equipe.

        1. Calcula os dois baldes da seção 10.4: 10 tentativas por e-mail a cada 15 minutos
           e 30 por IP por hora. A chave é o HMAC com o sal do dia, então nem o e-mail nem o
           IP ficam gravados.
        2. Transação 1: conta a tentativa nos dois baldes e, se não passou do limite, lê o
           usuário e o aceite dos Termos. Ela fecha antes do argon2.
        3. Limite estourado responde 429 com a mesma mensagem da senha errada.
        4. Confere a senha. Sem usuário, o argon2 roda contra um hash falso, para o tempo de
           resposta não dizer se o e-mail existe.
        5. Transação 2: grava a sessão (só o SHA-256 do segredo de 256 bits) e atualiza o
           `last_seen_at`, que a retenção de contas inativas usa (seção 11.6).

        Toda tentativa conta, inclusive a que acerta. Erros: `RateLimited` (429) e
        `Unauthenticated` (401), sempre com `INVALID_CREDENTIALS`.
        """
        if not self._hmac_key:
            raise RuntimeError("RATE_LIMIT_HMAC_KEY vazio.")
        # 1. Os baldes usam o dia UTC como sal e janelas fixas de tamanhos diferentes.
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

        # 2. Contadores e leitura do usuário confirmam juntos.
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

        # 3. O 429 não revela se o e-mail existe.
        if decision.limited:
            raise RateLimited(
                INVALID_CREDENTIALS,
                retry_after_seconds=decision.retry_after_seconds,
            )
        # 4. A senha é conferida antes de olhar se o usuário existe: os dois casos gastam
        # um argon2.
        if not self._password_matches(password, None if record is None else record.password_hash):
            raise Unauthenticated(INVALID_CREDENTIALS)
        if record is None:
            raise Unauthenticated(INVALID_CREDENTIALS)

        # 5. O cookie leva o segredo; o banco, só o hash dele. A equipe ganha 12 horas, e o
        # membro, 14 dias (seção 29.8).
        secret = new_session_secret()
        max_age = session_max_age_seconds(record.role)
        expires_at = now + timedelta(seconds=max_age)
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
            cookie=session_cookie(secret=secret, app_env=self._app_env, max_age=max_age),
        )

    async def authenticate(self, secret: str | None) -> Profile:
        """Perfil de quem está na sessão, com `needs_legal_acceptance`.

        Sem cookie, ou com sessão revogada, vencida ou de usuário apagado, responde 401
        (`Unauthenticated`). Uma transação curta de leitura. Não atualiza `last_seen_at`.
        """
        record = await self._active_user(secret)
        if record is None:
            raise Unauthenticated(UNAUTHENTICATED)
        return _profile(record)

    async def require_admin(self, secret: str | None) -> Profile:
        """Perfil de um admin: 401 sem sessão válida, 403 (`Forbidden`) para um membro."""
        profile = await self.authenticate(secret)
        if profile.role != "admin":
            raise Forbidden(FORBIDDEN)
        return profile

    async def logout(self, secret: str | None) -> None:
        """Revoga a sessão do cookie (seção 10.3). O controlador apaga o cookie.

        Grava `revoked_at` numa transação. Sem cookie, ou se nenhuma sessão ativa foi
        revogada, responde 401.
        """
        if not secret:
            raise Unauthenticated(UNAUTHENTICATED)
        now = self._clock.now()
        async with open_session(self._database_url) as session, UnitOfWork(session):
            revoked = await AuthSessionRepository(session).revoke(hash_session_secret(secret), now)
        if not revoked:
            raise Unauthenticated(UNAUTHENTICATED)

    def _password_matches(self, password: str, stored_hash: str | None) -> bool:
        """Confere a senha com o argon2id, gastando o mesmo trabalho sem usuário.

        Uma senha fora de 1 a 72 caracteres nem vai ao argon2. Sem hash gravado, verifica
        contra `dummy_hash` e devolve `False`.
        """
        if not password_is_checkable(password):
            return False
        if stored_hash is None:
            self._hasher.verify_password(password, self._hasher.dummy_hash)
            return False
        return self._hasher.verify_password(password, stored_hash)

    async def _active_user(self, secret: str | None) -> _UserRecord | None:
        """Lê sessão ativa, usuário e aceite dos Termos numa transação curta.

        A sessão é procurada pelo SHA-256 do segredo e precisa estar sem `revoked_at` e
        antes de `expires_at`. Devolve `None` quando falta qualquer peça.
        """
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
    """Primeiro admin e remoção de admin, pela linha de comando (seção 10.5).

    Os dois métodos pegam `pg_advisory_xact_lock`, um lock do PostgreSQL que dura até o fim
    da transação. Assim duas execuções simultâneas do pré-deploy não criam dois admins nem
    removem os dois últimos ao mesmo tempo.
    """

    def __init__(self, *, database_url: str, clock: Clock, hasher: PasswordHasher) -> None:
        self._database_url = database_url
        self._clock = clock
        self._hasher = hasher

    async def ensure(self, *, email: str, password: str) -> bool:
        """Cria o admin só quando nenhum existe. Devolve True se criou.

        Com um admin no banco, `ADMIN_EMAIL` e `ADMIN_PASSWORD` são ignoradas e nem
        precisam existir. Sem admin, valida as duas (`ValidationFailed`) e grava o usuário
        com `role = admin`. Tudo numa transação, com o hash argon2id calculado dentro dela,
        sob o lock.
        """
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
        """Remove o admin do e-mail, mas nunca o último.

        Numa transação sob o lock: `NotFound` se o e-mail não é de um admin, `Conflict` se
        ele é o único. As sessões saem antes do usuário porque a chave estrangeira de
        `auth_sessions` não tem cascata.
        """
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
    """Exige `ADMIN_EMAIL` válido e `ADMIN_PASSWORD` de 12 a 72 caracteres."""
    if not email.strip() or not password:
        raise ValidationFailed(ADMIN_CREDENTIALS_MISSING)
    if not email_is_valid(normalize_email(email)):
        raise ValidationFailed(ADMIN_EMAIL_INVALID)
    if not password_length_is_valid(password):
        raise ValidationFailed(ADMIN_PASSWORD_LENGTH)


async def _terms_version(session: AsyncSession, user_id: UUID) -> str | None:
    """A versão vigente se há aceite dela não revogado. `None` pede um novo aceite."""
    current = await ConsentRepository(session).has_current_terms(user_id, LEGAL_DOCUMENT_VERSION)
    if current:
        return LEGAL_DOCUMENT_VERSION
    return None


def _record(user: User, terms_version: str | None) -> _UserRecord:
    """Copia a entidade do ORM, para o serviço não usá-la depois que a sessão fecha."""
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
    """O perfil público, sem o hash da senha (seção 12)."""
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
