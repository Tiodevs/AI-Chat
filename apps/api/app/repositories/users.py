"""Consultas de users. Seção 8.1 do SDD."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        return await self._session.scalar(select(User).where(User.email == email))

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def touch(self, user_id: UUID, now: datetime) -> None:
        await self._session.execute(
            update(User).where(User.id == user_id).values(last_seen_at=now, updated_at=now)
        )

    async def count_by_role(self, role: str) -> int:
        value = await self._session.scalar(
            select(func.count()).select_from(User).where(User.role == role)
        )
        return int(value or 0)

    async def insert(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: str,
        role: str,
        now: datetime,
    ) -> None:
        self._session.add(
            User(
                email=email,
                password_hash=password_hash,
                full_name=full_name,
                role=role,
                phone=None,
                visitor_type=None,
                visit_reason=None,
                last_seen_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        await self._session.flush()

    async def delete_user(self, user_id: UUID) -> None:
        await self._session.execute(delete(User).where(User.id == user_id))
