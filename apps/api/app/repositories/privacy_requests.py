"""Pedidos de titular. Seções 8.1 e 12 do SDD."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, or_, select
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

    async def queue(self, *, closed_limit: int) -> list[DataSubjectRequest]:
        """Abertos e em andamento, do prazo mais antigo ao mais novo, e os fechados mais recentes.

        Os atrasados têm o prazo mais antigo, então ficam primeiro. Uma consulta só, para os
        abertos e os fechados saírem do mesmo instante do banco: um pedido fechado no meio da
        leitura não aparece duas vezes.
        """
        request = DataSubjectRequest
        is_open = request.status.in_(OPEN_STATUSES)
        recent_closed = (
            select(request.id)
            .where(request.status.in_(CLOSED_STATUSES))
            .order_by(request.closed_at.desc().nulls_last(), request.id)
            .limit(closed_limit)
        )
        result = await self._session.scalars(
            select(request)
            .where(or_(is_open, request.id.in_(recent_closed)))
            .order_by(
                case((is_open, 0), else_=1),
                case((is_open, request.due_at), else_=None).asc().nulls_last(),
                request.closed_at.desc().nulls_last(),
                request.received_at,
                request.id,
            )
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
