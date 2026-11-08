"""O admin inicial é criado uma vez e o último não sai. Seções 6.4 e 10.5 do SDD.

Usa o `BootstrapAdminService` de verdade, o mesmo do script `bootstrap_admin` do pré-deploy.
`_demote_admins` rebaixa os admins que já existem no banco e `_restore_admins` os devolve no
fim. A corrida roda dois `ensure` com `asyncio.gather`, e o `pg_advisory_xact_lock` deixa só um
criar o admin. Precisa de PostgreSQL com pgvector local (`migrated_database`); sem ele pula, e
com `REQUIRE_INTEGRATION_DB=1` falha.
"""

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from app.adapters.clock import SystemClock
from app.adapters.password_hasher import get_password_hasher
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.errors import Conflict, ValidationFailed
from app.models.user import User
from app.prompts.auth import ADMIN_LAST, ADMIN_PASSWORD_LENGTH
from app.repositories.auth_sessions import AuthSessionRepository
from app.repositories.users import UserRepository
from app.services.auth import BootstrapAdminService

pytestmark = pytest.mark.integration

PASSWORD = "admin-password-1"


def test_bootstrap_creates_one_admin_and_refuses_to_remove_the_last(
    migrated_database: str,
) -> None:
    email = _email()
    second = _email()
    previous = _run(_demote_admins(migrated_database))
    service = _service(migrated_database)
    try:
        with pytest.raises(ValidationFailed, match=ADMIN_PASSWORD_LENGTH):
            _run(service.ensure(email=email, password="short"))
        assert _run(service.ensure(email=email, password=PASSWORD)) is True
        assert _run(service.ensure(email=email, password=PASSWORD)) is False
        with pytest.raises(Conflict, match=ADMIN_LAST):
            _run(service.remove(email))
        _run(_insert_admin(migrated_database, email=second))
        _run(service.remove(email))
        with pytest.raises(Conflict, match=ADMIN_LAST):
            _run(service.remove(second))
        assert _run(_count_admins(migrated_database)) == 1
    finally:
        _run(_delete_email(migrated_database, email))
        _run(_delete_email(migrated_database, second))
        _run(_restore_admins(migrated_database, previous))


def test_concurrent_bootstrap_creates_a_single_admin(migrated_database: str) -> None:
    email = _email()
    previous = _run(_demote_admins(migrated_database))
    try:
        created = asyncio.run(_create_together(migrated_database, email))
        assert sorted(created) == [False, True]
        assert _run(_count_email(migrated_database, email)) == 1
    finally:
        _run(_delete_email(migrated_database, email))
        _run(_restore_admins(migrated_database, previous))


def _service(database_url: str) -> BootstrapAdminService:
    """O `BootstrapAdminService` de verdade, com o relógio do sistema e o argon2id."""
    return BootstrapAdminService(
        database_url=database_url,
        clock=SystemClock(),
        hasher=get_password_hasher(),
    )


def _email() -> str:
    """E-mail único de admin, num domínio que só este arquivo usa."""
    return f"admin-{uuid4().hex}@bootstrap.test"


def _run[T](coro: Coroutine[object, object, T]) -> T:
    """Roda a corrotina num loop novo e devolve o resultado."""
    return asyncio.run(coro)


async def _create_together(database_url: str, email: str) -> list[bool]:
    """Roda dois `ensure` ao mesmo tempo e devolve o que cada um respondeu."""
    first, second = await asyncio.gather(
        _service(database_url).ensure(email=email, password=PASSWORD),
        _service(database_url).ensure(email=email, password=PASSWORD),
    )
    return [first, second]


async def _demote_admins(database_url: str) -> list[UUID]:
    """Rebaixa a `member` todos os admins do banco e devolve os ids deles.

    O serviço só cria um admin quando não há nenhum (seção 10.5), então o teste começa sem
    admin. `_restore_admins` devolve o papel no fim.
    """
    async with open_session(database_url) as session, UnitOfWork(session):
        found = await session.scalars(select(User.id).where(User.role == "admin"))
        ids = list(found.all())
        if ids:
            await session.execute(update(User).where(User.id.in_(ids)).values(role="member"))
    return ids


async def _restore_admins(database_url: str, ids: list[UUID]) -> None:
    """Devolve o papel `admin` aos ids rebaixados por `_demote_admins`."""
    if not ids:
        return
    async with open_session(database_url) as session, UnitOfWork(session):
        await session.execute(update(User).where(User.id.in_(ids)).values(role="admin"))


async def _insert_admin(database_url: str, *, email: str) -> None:
    """Grava um segundo admin, para o primeiro poder sair."""
    async with open_session(database_url) as session, UnitOfWork(session):
        await UserRepository(session).insert(
            email=email,
            password_hash=get_password_hasher().hash_password(PASSWORD),
            full_name="Outro Admin",
            role="admin",
            now=datetime.now(UTC),
        )


async def _delete_email(database_url: str, email: str) -> None:
    """Apaga o usuário pelo e-mail, com as sessões dele."""
    async with open_session(database_url) as session, UnitOfWork(session):
        users = UserRepository(session)
        user = await users.get_by_email(email)
        if user is None:
            return
        await AuthSessionRepository(session).delete_for_user(user.id)
        await users.delete_user(user.id)


async def _count_admins(database_url: str) -> int:
    """Quantos usuários têm o papel `admin`."""
    async with open_session(database_url) as session, UnitOfWork(session):
        count = await UserRepository(session).count_by_role("admin")
    return count


async def _count_email(database_url: str, email: str) -> int:
    """1 se existe usuário com o e-mail, 0 se não."""
    async with open_session(database_url) as session, UnitOfWork(session):
        user = await UserRepository(session).get_by_email(email)
    return 0 if user is None else 1
