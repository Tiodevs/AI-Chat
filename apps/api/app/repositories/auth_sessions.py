"""Sessões de autenticação. O banco guarda o SHA-256 do segredo. Seção 8.1."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_session import AuthSession


class AuthSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        token_hash: str,
        user_id: UUID,
        expires_at: datetime,
        user_agent: str,
    ) -> None:
        self._session.add(
            AuthSession(
                token_hash=token_hash,
                user_id=user_id,
                expires_at=expires_at,
                user_agent=user_agent,
            )
        )
        await self._session.flush()

    async def get_active(self, token_hash: str, now: datetime) -> AuthSession | None:
        return await self._session.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
        )

    async def revoke(self, token_hash: str, now: datetime) -> bool:
        result = await self._session.execute(
            update(AuthSession)
            .where(
                AuthSession.token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
            .values(revoked_at=now)
            .returning(AuthSession.id)
        )
        return result.scalar_one_or_none() is not None

    async def delete_for_user(self, user_id: UUID) -> None:
        await self._session.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
