"""Pedidos de titular. Seções 8.1 e 12 do SDD."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.privacy import CLOSED_STATUSES, OPEN_STATUSES
from app.models.data_subject_request import DataSubjectRequest


class PrivacyRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        *,
        user_id: UUID | None,
        contact_email: str,
        request_type: str,
        description: str,
        status: str,
        received_at: datetime,
        due_at: datetime,
    ) -> DataSubjectRequest:
        row = DataSubjectRequest(
            user_id=user_id,
            contact_email=contact_email,
            request_type=request_type,
            description=description,
            status=status,
            received_at=received_at,
            due_at=due_at,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def open_queue(self) -> list[DataSubjectRequest]:
        """Abertos e em andamento, do prazo mais antigo ao mais novo.

        Os atrasados são os de prazo mais antigo, então ficam primeiro.
        """
        result = await self._session.scalars(
            select(DataSubjectRequest)
            .where(DataSubjectRequest.status.in_(OPEN_STATUSES))
            .order_by(DataSubjectRequest.due_at, DataSubjectRequest.received_at)
        )
        return list(result.all())

    async def recently_closed(self, limit: int) -> list[DataSubjectRequest]:
        """Os fechados mais recentes, do fechamento mais novo ao mais antigo."""
        result = await self._session.scalars(
            select(DataSubjectRequest)
            .where(DataSubjectRequest.status.in_(CLOSED_STATUSES))
            .order_by(DataSubjectRequest.closed_at.desc().nulls_last(), DataSubjectRequest.id)
            .limit(limit)
        )
        return list(result.all())

    async def lock(self, request_id: UUID) -> DataSubjectRequest | None:
        """Lê o pedido com trava de linha, para dois admins não fecharem o mesmo ao mesmo tempo."""
        return await self._session.scalar(
            select(DataSubjectRequest)
            .where(DataSubjectRequest.id == request_id)
            .with_for_update()
        )

    async def apply(
        self,
        row: DataSubjectRequest,
        *,
        status: str,
        resolution_note: str | None,
        closed_at: datetime | None,
    ) -> DataSubjectRequest:
        row.status = status
        row.resolution_note = resolution_note
        row.closed_at = closed_at
        await self._session.flush()
        return row
