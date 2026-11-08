"""Cada regra de retenção apaga só o que venceu. Seção 11.6 e linha da 21.1 do SDD.

Usa o `RetentionService` de verdade com o relógio parado no instante da importação. Os helpers
gravam linhas pelos modelos com datas um pouco antes e um pouco depois de cada prazo, e cada
teste roda uma regra e confere os dois lados. Atenção: `run_rule` vale para o banco inteiro,
não só para as linhas do teste, e grava uma linha em `retention_runs`. O primeiro teste não usa
banco; os outros precisam de PostgreSQL com pgvector local (`migrated_database`), pulam sem
ele e falham com `REQUIRE_INTEGRATION_DB=1`.
"""

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.retention import RetentionRule
from app.models.audit_event import AuditEvent
from app.models.auth_session import AuthSession
from app.models.conversation import Conversation
from app.models.data_subject_request import DataSubjectRequest
from app.models.guest_key import GuestKey
from app.models.message import Message
from app.models.rate_limit_window import RateLimitWindow
from app.models.registration_session import RegistrationSession
from app.models.user import User
from app.services.retention import RULES, RetentionService

pytestmark = pytest.mark.integration

NOW = datetime.now(UTC).replace(microsecond=0)


class FrozenClock:
    """Relógio parado em `NOW`: as datas dos helpers e os cortes das regras saem dele."""

    def now(self) -> datetime:
        return NOW


def _ago(**kwargs: float) -> datetime:
    """Instante `NOW` menos o intervalo dado."""
    return NOW - timedelta(**kwargs)


def _run(coro: Coroutine[object, object, Any]) -> Any:
    """Roda a corrotina num loop novo e devolve o resultado."""
    return asyncio.run(coro)


def _service(database_url: str) -> RetentionService:
    """O `RetentionService` de verdade, com o relógio parado."""
    return RetentionService(database_url=database_url, clock=FrozenClock())


def test_every_rule_of_section_11_6_runs() -> None:
    assert {rule for rule, _ in RULES} == set(RetentionRule)


def test_inactive_member_accounts_go_but_admins_and_active_members_stay(
    migrated_database: str,
) -> None:
    stale = _run(_user(migrated_database, last_seen=_ago(days=731)))
    admin = _run(_user(migrated_database, last_seen=_ago(days=731), role="admin"))
    active = _run(_user(migrated_database, last_seen=_ago(days=729)))
    # `auth_sessions` não apaga em cascata: a regra apaga a sessão do inativo antes dele.
    _run(_auth_session(migrated_database, stale, expires_at=NOW + timedelta(days=1)))
    try:
        result = _run(_service(migrated_database).run_rule(RetentionRule.INACTIVE_ACCOUNTS))
        assert result.deleted_count >= 1
        assert _run(_exists(migrated_database, User, stale)) is False
        assert _run(_exists(migrated_database, User, admin)) is True
        assert _run(_exists(migrated_database, User, active)) is True
    finally:
        _run(_purge_users(migrated_database, [stale, admin, active]))


def test_member_conversations_expire_twelve_months_after_the_last_message(
    migrated_database: str,
) -> None:
    """A última atividade é a mensagem mais nova, ou a criação numa conversa sem mensagem."""
    owner = _run(_user(migrated_database, last_seen=NOW))
    old = _run(_conversation(migrated_database, user_id=owner, created=_ago(days=400)))
    _run(_message(migrated_database, old, created=_ago(days=366)))
    revived = _run(_conversation(migrated_database, user_id=owner, created=_ago(days=400)))
    _run(_message(migrated_database, revived, created=_ago(days=10)))
    empty_old = _run(_conversation(migrated_database, user_id=owner, created=_ago(days=366)))
    fresh = _run(_conversation(migrated_database, user_id=owner, created=_ago(days=1)))
    try:
        _run(_service(migrated_database).run_rule(RetentionRule.MEMBER_CONVERSATIONS))
        assert _run(_exists(migrated_database, Conversation, old)) is False
        assert _run(_exists(migrated_database, Conversation, empty_old)) is False
        assert _run(_exists(migrated_database, Conversation, revived)) is True
        assert _run(_exists(migrated_database, Conversation, fresh)) is True
    finally:
        _run(_purge_users(migrated_database, [owner]))


def test_guest_conversations_expire_in_thirty_days_and_member_ones_stay(
    migrated_database: str,
) -> None:
    key = _run(_guest_key(migrated_database, created=NOW))
    owner = _run(_user(migrated_database, last_seen=NOW))
    old_guest = _run(_conversation(migrated_database, guest_key_id=key, created=_ago(days=31)))
    new_guest = _run(_conversation(migrated_database, guest_key_id=key, created=_ago(days=29)))
    member = _run(_conversation(migrated_database, user_id=owner, created=_ago(days=31)))
    try:
        _run(_service(migrated_database).run_rule(RetentionRule.GUEST_CONVERSATIONS))
        assert _run(_exists(migrated_database, Conversation, old_guest)) is False
        assert _run(_exists(migrated_database, Conversation, new_guest)) is True
        assert _run(_exists(migrated_database, Conversation, member)) is True
    finally:
        _run(_purge_users(migrated_database, [owner]))
        _run(_delete(migrated_database, GuestKey, [key]))


def test_expired_guest_keys_go_and_member_conversations_keep_their_owner(
    migrated_database: str,
) -> None:
    old_key = _run(_guest_key(migrated_database, created=_ago(days=31)))
    new_key = _run(_guest_key(migrated_database, created=_ago(days=29)))
    owner = _run(_user(migrated_database, last_seen=NOW))
    # Conversa de membro que ainda guarda a chave vencida. A chave estrangeira apaga em cascata,
    # então a regra solta a conversa antes de apagar a chave.
    attached = _run(
        _conversation(migrated_database, user_id=owner, guest_key_id=old_key, created=NOW)
    )
    try:
        _run(_service(migrated_database).run_rule(RetentionRule.GUEST_KEYS))
        assert _run(_exists(migrated_database, GuestKey, old_key)) is False
        assert _run(_exists(migrated_database, GuestKey, new_key)) is True
        assert _run(_exists(migrated_database, Conversation, attached)) is True
    finally:
        _run(_purge_users(migrated_database, [owner]))
        _run(_delete(migrated_database, GuestKey, [new_key]))


def test_registration_sessions_go_after_they_expire(migrated_database: str) -> None:
    expired = _run(_registration(migrated_database, expires_at=_ago(seconds=1)))
    open_one = _run(_registration(migrated_database, expires_at=NOW + timedelta(hours=1)))
    try:
        _run(_service(migrated_database).run_rule(RetentionRule.REGISTRATION_SESSIONS))
        assert _run(_exists(migrated_database, RegistrationSession, expired)) is False
        assert _run(_exists(migrated_database, RegistrationSession, open_one)) is True
    finally:
        _run(_delete(migrated_database, RegistrationSession, [open_one]))


def test_auth_sessions_go_fourteen_days_after_expiring_or_being_revoked(
    migrated_database: str,
) -> None:
    owner = _run(_user(migrated_database, last_seen=NOW))
    expired = _run(_auth_session(migrated_database, owner, expires_at=_ago(days=15)))
    revoked = _run(
        _auth_session(
            migrated_database,
            owner,
            expires_at=NOW + timedelta(days=1),
            revoked_at=_ago(days=15),
        )
    )
    recent = _run(_auth_session(migrated_database, owner, expires_at=_ago(days=13)))
    active = _run(_auth_session(migrated_database, owner, expires_at=NOW + timedelta(days=1)))
    try:
        _run(_service(migrated_database).run_rule(RetentionRule.AUTH_SESSIONS))
        assert _run(_exists(migrated_database, AuthSession, expired)) is False
        assert _run(_exists(migrated_database, AuthSession, revoked)) is False
        assert _run(_exists(migrated_database, AuthSession, recent)) is True
        assert _run(_exists(migrated_database, AuthSession, active)) is True
    finally:
        _run(_purge_users(migrated_database, [owner]))


def test_rate_limit_windows_go_after_forty_eight_hours(migrated_database: str) -> None:
    old_key = f"retention-old-{uuid4().hex}"
    new_key = f"retention-new-{uuid4().hex}"
    _run(_window(migrated_database, old_key, _ago(hours=49)))
    _run(_window(migrated_database, new_key, _ago(hours=47)))
    try:
        _run(_service(migrated_database).run_rule(RetentionRule.RATE_LIMIT_WINDOWS))
        assert _run(_window_exists(migrated_database, old_key)) is False
        assert _run(_window_exists(migrated_database, new_key)) is True
    finally:
        _run(_delete_windows(migrated_database, [old_key, new_key]))


def test_audit_events_go_after_two_years(migrated_database: str) -> None:
    old = _run(_audit(migrated_database, created=_ago(days=731)))
    recent = _run(_audit(migrated_database, created=_ago(days=729)))
    try:
        _run(_service(migrated_database).run_rule(RetentionRule.AUDIT_EVENTS))
        assert _run(_exists(migrated_database, AuditEvent, old)) is False
        assert _run(_exists(migrated_database, AuditEvent, recent)) is True
    finally:
        _run(_delete(migrated_database, AuditEvent, [recent]))


def test_privacy_requests_go_two_years_after_closing_and_open_ones_stay(
    migrated_database: str,
) -> None:
    closed_old = _run(_privacy_request(migrated_database, closed_at=_ago(days=731)))
    closed_recent = _run(_privacy_request(migrated_database, closed_at=_ago(days=729)))
    open_old = _run(_privacy_request(migrated_database, closed_at=None))
    try:
        _run(_service(migrated_database).run_rule(RetentionRule.PRIVACY_REQUESTS))
        assert _run(_exists(migrated_database, DataSubjectRequest, closed_old)) is False
        assert _run(_exists(migrated_database, DataSubjectRequest, closed_recent)) is True
        assert _run(_exists(migrated_database, DataSubjectRequest, open_old)) is True
    finally:
        _run(_delete(migrated_database, DataSubjectRequest, [closed_recent, open_old]))


def test_run_all_reports_one_result_per_rule(migrated_database: str) -> None:
    results = _run(_service(migrated_database).run_all())
    assert [result.rule for result in results] == [rule for rule, _ in RULES]
    assert all(result.deleted_count >= 0 for result in results)


async def _user(database_url: str, *, last_seen: datetime, role: str = "member") -> UUID:
    """Grava um usuário com o `last_seen_at` e o papel dados. Devolve o id."""
    user_id = uuid4()
    async with open_session(database_url) as session, UnitOfWork(session):
        session.add(
            User(
                id=user_id,
                email=f"retention-{user_id.hex}@example.com",
                password_hash="$argon2id$not-used",
                full_name="Retenção Teste",
                role=role,
                last_seen_at=last_seen,
                created_at=last_seen,
                updated_at=last_seen,
            )
        )
    return user_id


async def _auth_session(
    database_url: str,
    user_id: UUID,
    *,
    expires_at: datetime,
    revoked_at: datetime | None = None,
) -> UUID:
    """Grava uma sessão do usuário com as datas dadas. Devolve o id."""
    row = AuthSession(
        token_hash=uuid4().hex,
        user_id=user_id,
        expires_at=expires_at,
        revoked_at=revoked_at,
        user_agent="pytest",
    )
    async with open_session(database_url) as session, UnitOfWork(session):
        session.add(row)
        await session.flush()
        row_id = row.id
    return row_id


async def _guest_key(database_url: str, *, created: datetime) -> UUID:
    """Grava uma chave de convidado criada em `created`. Devolve o id."""
    row = GuestKey(token_hash=uuid4().hex, created_at=created)
    async with open_session(database_url) as session, UnitOfWork(session):
        session.add(row)
        await session.flush()
        row_id = row.id
    return row_id


async def _conversation(
    database_url: str,
    *,
    created: datetime,
    user_id: UUID | None = None,
    guest_key_id: UUID | None = None,
) -> UUID:
    """Grava uma conversa do membro, do convidado ou dos dois. Devolve o id."""
    row = Conversation(user_id=user_id, guest_key_id=guest_key_id, created_at=created)
    async with open_session(database_url) as session, UnitOfWork(session):
        session.add(row)
        await session.flush()
        row_id = row.id
    return row_id


async def _message(database_url: str, conversation_id: UUID, *, created: datetime) -> None:
    """Grava uma pergunta do visitante na conversa, em `created`."""
    async with open_session(database_url) as session, UnitOfWork(session):
        session.add(
            Message(
                id=uuid4(),
                conversation_id=conversation_id,
                client_message_id=uuid4(),
                role="user",
                content="Qual é o horário de visita?",
                citations=[],
                input_tokens=0,
                output_tokens=0,
                created_at=created,
            )
        )


async def _registration(database_url: str, *, expires_at: datetime) -> UUID:
    """Grava uma sessão de cadastro que expira em `expires_at`. Devolve o id."""
    row_id = uuid4()
    async with open_session(database_url) as session, UnitOfWork(session):
        session.add(
            RegistrationSession(
                id=row_id,
                status="collecting_required",
                path="chat",
                fields={},
                password_hash=None,
                transcript=[],
                user_id=None,
                expires_at=expires_at,
            )
        )
    return row_id


async def _window(database_url: str, key: str, start: datetime) -> None:
    """Grava uma janela de limite com uma contagem, começando em `start`."""
    async with open_session(database_url) as session, UnitOfWork(session):
        session.add(RateLimitWindow(bucket_key=key, window_start=start, count=1))


async def _window_exists(database_url: str, key: str) -> bool:
    """Se a janela desta chave ainda existe."""
    async with open_session(database_url) as session:
        found = await session.scalar(
            select(RateLimitWindow.bucket_key).where(RateLimitWindow.bucket_key == key)
        )
    return found is not None


async def _delete_windows(database_url: str, keys: list[str]) -> None:
    """Apaga as janelas destas chaves."""
    async with open_session(database_url) as session, UnitOfWork(session):
        await session.execute(delete(RateLimitWindow).where(RateLimitWindow.bucket_key.in_(keys)))


async def _audit(database_url: str, *, created: datetime) -> UUID:
    """Grava um evento `account.delete` com ator e alvo aleatórios. Devolve o id."""
    row = AuditEvent(
        actor_user_id=uuid4(),
        action="account.delete",
        target_type="user",
        target_id=uuid4(),
        created_at=created,
    )
    async with open_session(database_url) as session, UnitOfWork(session):
        session.add(row)
        await session.flush()
        row_id = row.id
    return row_id


async def _privacy_request(database_url: str, *, closed_at: datetime | None) -> UUID:
    """Grava um pedido recebido há 800 dias, fechado em `closed_at` ou ainda aberto."""
    received = _ago(days=800)
    row = DataSubjectRequest(
        user_id=None,
        contact_email="titular@example.com",
        request_type="deletion",
        description="Pedido de teste.",
        status="open" if closed_at is None else "done",
        received_at=received,
        due_at=received + timedelta(days=15),
        closed_at=closed_at,
    )
    async with open_session(database_url) as session, UnitOfWork(session):
        session.add(row)
        await session.flush()
        row_id = row.id
    return row_id


async def _exists(database_url: str, model: Any, row_id: UUID) -> bool:
    """Se a linha deste modelo e deste id ainda existe."""
    async with open_session(database_url) as session:
        found = await session.get(model, row_id)
    return found is not None


async def _delete(database_url: str, model: Any, ids: list[UUID]) -> None:
    """Apaga as linhas deste modelo pelos ids."""
    async with open_session(database_url) as session, UnitOfWork(session):
        await session.execute(delete(model).where(model.id.in_(ids)))


async def _purge_users(database_url: str, ids: list[UUID]) -> None:
    """Apaga os usuários e as sessões deles. O resto cai em cascata."""
    async with open_session(database_url) as session, UnitOfWork(session):
        await session.execute(delete(AuthSession).where(AuthSession.user_id.in_(ids)))
        await session.execute(delete(User).where(User.id.in_(ids)))
