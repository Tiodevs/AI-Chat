"""Eventos de auditoria. Seção 8.1 do SDD."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_event import AuditEvent


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        actor_user_id: UUID,
        action: str,
        target_type: str,
        target_id: UUID,
        created_at: datetime,
        reason: str | None = None,
    ) -> None:
        self._session.add(
            AuditEvent(
                actor_user_id=actor_user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                reason=reason,
                created_at=created_at,
            )
        )
        await self._session.flush()
