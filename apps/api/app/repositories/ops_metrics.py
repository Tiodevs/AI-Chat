"""Leituras agregadas para o /metrics. Seção 18.3 do SDD."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.privacy import RequestStatus
from app.models.data_subject_request import DataSubjectRequest
from app.models.retention_run import RetentionRun

_OPEN_STATUSES = (RequestStatus.OPEN.value, RequestStatus.IN_PROGRESS.value)


class OpsMetricsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def open_requests(self, now: datetime) -> tuple[int, int]:
        """Pedidos de titular abertos: (dentro do prazo, atrasados)."""
        overdue = DataSubjectRequest.due_at < now
        rows = await self._session.execute(
            select(overdue, func.count())
            .where(DataSubjectRequest.status.in_(_OPEN_STATUSES))
            .group_by(overdue)
        )
        counts = {bool(flag): int(total) for flag, total in rows.all()}
        return counts.get(False, 0), counts.get(True, 0)

    async def retention_deleted_by_rule(self) -> dict[str, int]:
        rows = await self._session.execute(
            select(RetentionRun.rule, func.sum(RetentionRun.deleted_count)).group_by(
                RetentionRun.rule
            )
        )
        return {rule: int(total or 0) for rule, total in rows.all()}

    async def last_retention_run(self) -> datetime | None:
        return await self._session.scalar(select(func.max(RetentionRun.ran_at)))
