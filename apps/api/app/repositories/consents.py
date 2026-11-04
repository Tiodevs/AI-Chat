"""Registros de consentimento. Revogar grava revoked_at. Seção 8.1."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.registration import ConsentGrant, Purpose
from app.models.consent_record import ConsentRecord


class ConsentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_current_terms(self, user_id: UUID, version: str) -> bool:
        found = await self._session.scalar(
            select(ConsentRecord.id).where(
                ConsentRecord.user_id == user_id,
                ConsentRecord.purpose == Purpose.TERMS.value,
                ConsentRecord.document_version == version,
                ConsentRecord.revoked_at.is_(None),
            )
        )
        return found is not None

    async def insert_grants(
        self,
        *,
        user_id: UUID,
        grants: tuple[ConsentGrant, ...],
        source: str,
        granted_at: datetime,
    ) -> None:
        for grant in grants:
            self._session.add(
                ConsentRecord(
                    id=uuid4(),
                    user_id=user_id,
                    purpose=grant.purpose,
                    document_version=grant.document_version,
                    granted_at=granted_at,
                    revoked_at=None,
                    source=source,
                )
            )
        await self._session.flush()

    async def list_for_user(self, user_id: UUID) -> list[ConsentRecord]:
        rows = await self._session.scalars(
            select(ConsentRecord)
            .where(ConsentRecord.user_id == user_id)
            .order_by(ConsentRecord.granted_at.asc(), ConsentRecord.id.asc())
        )
        return list(rows)

    async def has_active(self, user_id: UUID, purpose: str, version: str | None = None) -> bool:
        query = select(ConsentRecord.id).where(
            ConsentRecord.user_id == user_id,
            ConsentRecord.purpose == purpose,
            ConsentRecord.revoked_at.is_(None),
        )
        if version is not None:
            query = query.where(ConsentRecord.document_version == version)
        return await self._session.scalar(query.limit(1)) is not None

    async def revoke(self, user_id: UUID, purpose: str, revoked_at: datetime) -> bool:
        """Revoga todas as concessões vigentes do propósito. Devolve se alguma mudou."""
        result = await self._session.execute(
            update(ConsentRecord)
            .where(
                ConsentRecord.user_id == user_id,
                ConsentRecord.purpose == purpose,
                ConsentRecord.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
            .returning(ConsentRecord.id)
        )
        return result.first() is not None
