"""O admin inicial é criado uma vez e o último não sai. Seção 10.5 do SDD."""

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
    return BootstrapAdminService(
        database_url=database_url,
        clock=SystemClock(),
        hasher=get_password_hasher(),
    )


def _email() -> str:
    return f"admin-{uuid4().hex}@bootstrap.test"


def _run[T](coro: Coroutine[object, object, T]) -> T:
    return asyncio.run(coro)


async def _create_together(database_url: str, email: str) -> list[bool]:
    first, second = await asyncio.gather(
        _service(database_url).ensure(email=email, password=PASSWORD),
        _service(database_url).ensure(email=email, password=PASSWORD),
    )
    return [first, second]


async def _demote_admins(database_url: str) -> list[UUID]:
    async with open_session(database_url) as session, UnitOfWork(session):
        found = await session.scalars(select(User.id).where(User.role == "admin"))
        ids = list(found.all())
        if ids:
            await session.execute(update(User).where(User.id.in_(ids)).values(role="member"))
    return ids


async def _restore_admins(database_url: str, ids: list[UUID]) -> None:
    if not ids:
        return
    async with open_session(database_url) as session, UnitOfWork(session):
        await session.execute(update(User).where(User.id.in_(ids)).values(role="admin"))


async def _insert_admin(database_url: str, *, email: str) -> None:
    async with open_session(database_url) as session, UnitOfWork(session):
        await UserRepository(session).insert(
            email=email,
            password_hash=get_password_hasher().hash_password(PASSWORD),
            full_name="Outro Admin",
            role="admin",
            now=datetime.now(UTC),
        )


async def _delete_email(database_url: str, email: str) -> None:
    async with open_session(database_url) as session, UnitOfWork(session):
        users = UserRepository(session)
        user = await users.get_by_email(email)
        if user is None:
            return
        await AuthSessionRepository(session).delete_for_user(user.id)
        await users.delete_user(user.id)


async def _count_admins(database_url: str) -> int:
    async with open_session(database_url) as session, UnitOfWork(session):
        count = await UserRepository(session).count_by_role("admin")
    return count


async def _count_email(database_url: str, email: str) -> int:
    async with open_session(database_url) as session, UnitOfWork(session):
        user = await UserRepository(session).get_by_email(email)
    return 0 if user is None else 1
