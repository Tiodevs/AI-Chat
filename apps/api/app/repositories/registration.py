"""Sessões de cadastro. O serializador da transcrição não tem senha. Seção 8.1."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.registration_session import RegistrationSession


@dataclass(frozen=True, slots=True)
class RegistrationRecord:
    id: UUID
    status: str
    path: str
    fields: dict[str, Any]
    password_hash: str | None
    transcript: list[Any]
    user_id: UUID | None
    expires_at: datetime


class RegistrationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        *,
        session_id: UUID,
        status: str,
        path: str,
        fields: dict[str, Any],
        password_hash: str | None,
        transcript: list[Any],
        user_id: UUID | None,
        expires_at: datetime,
    ) -> RegistrationRecord:
        row = RegistrationSession(
            id=session_id,
            status=status,
            path=path,
            fields=fields,
            password_hash=password_hash,
            transcript=transcript,
            user_id=user_id,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _record(row)

    async def get(self, session_id: UUID) -> RegistrationRecord | None:
        row = await self._session.get(RegistrationSession, session_id)
        if row is None:
            return None
        return _record(row)

    async def lock(self, session_id: UUID) -> RegistrationRecord | None:
        row = await self._session.scalar(
            select(RegistrationSession)
            .where(RegistrationSession.id == session_id)
            .with_for_update()
        )
        if row is None:
            return None
        return _record(row)

    async def save(self, record: RegistrationRecord) -> RegistrationRecord:
        await self._session.execute(
            update(RegistrationSession)
            .where(RegistrationSession.id == record.id)
            .values(
                status=record.status,
                path=record.path,
                fields=record.fields,
                password_hash=record.password_hash,
                transcript=record.transcript,
                user_id=record.user_id,
                expires_at=record.expires_at,
            )
        )
        return record


def _record(row: RegistrationSession) -> RegistrationRecord:
    fields = dict(row.fields)
    transcript = [dict(item) for item in row.transcript if isinstance(item, dict)]
    return RegistrationRecord(
        id=row.id,
        status=row.status,
        path=row.path,
        fields=fields,
        password_hash=row.password_hash,
        transcript=transcript,
        user_id=row.user_id,
        expires_at=row.expires_at,
    )
