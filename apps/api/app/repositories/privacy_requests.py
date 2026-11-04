"""Pedidos de titular. Seção 8.1 do SDD."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

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
