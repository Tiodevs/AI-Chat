"""Leituras agregadas para o /metrics. Seção 18.3 do SDD.

Camada de repositório (seção 6.2 do SDD). Lê `data_subject_requests` e `retention_runs`. Quem
usa é `refresh_database_metrics`, que o `GET /metrics` chama a cada coleta do Prometheus. Essas
métricas vêm do banco porque o `retention-job` roda em outro processo, que a coleta não
alcança.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.privacy import RequestStatus
from app.models.data_subject_request import DataSubjectRequest
from app.models.retention_run import RetentionRun

# Status de um pedido ainda aberto: `open` e `in_progress`.
_OPEN_STATUSES = (RequestStatus.OPEN.value, RequestStatus.IN_PROGRESS.value)


class OpsMetricsRepository:
    """Contagens do banco para as métricas `atrium_dsr_open` e `atrium_retention_*`."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def open_requests(self, now: datetime) -> tuple[int, int]:
        """Pedidos de titular abertos: (dentro do prazo, atrasados).

        Agrupa pelo próprio teste `due_at < now`, que vale verdadeiro para os atrasados.
        Alimenta `atrium_dsr_open{overdue}` e o alerta de pedido atrasado.
        """
        overdue = DataSubjectRequest.due_at < now
        rows = await self._session.execute(
            select(overdue, func.count())
            .where(DataSubjectRequest.status.in_(_OPEN_STATUSES))
            .group_by(overdue)
        )
        counts = {bool(flag): int(total) for flag, total in rows.all()}
        return counts.get(False, 0), counts.get(True, 0)

    async def retention_deleted_by_rule(self) -> dict[str, int]:
        """Total apagado por regra, somando todas as execuções já gravadas.

        Como `retention_runs` nunca é apagada, a soma só cresce, como um contador do
        Prometheus (`atrium_retention_deleted`).
        """
        rows = await self._session.execute(
            select(RetentionRun.rule, func.sum(RetentionRun.deleted_count)).group_by(
                RetentionRun.rule
            )
        )
        return {rule: int(total or 0) for rule, total in rows.all()}

    async def last_retention_run(self) -> datetime | None:
        """Horário da execução mais recente, ou `None` se o job nunca rodou.

        Usa `retention_runs_ran_at_idx`. Alimenta o alerta de retenção parada (seção 18.3).
        """
        return await self._session.scalar(select(func.max(RetentionRun.ran_at)))

    async def handoff_counts(self, now: datetime) -> tuple[int, int]:
        """Atendimentos na fila e pessoas da equipe presentes (seção 29.12).

        Alimentam `atrium_handoff_queue`, `atrium_handoff_attendants_available` e o alerta
        Fila sem equipe. Vêm do banco para valerem com mais de uma réplica.
        """
        from app.repositories.handoffs import HandoffRepository

        handoffs = HandoffRepository(self._session)
        return await handoffs.count_queued(), await handoffs.count_present_staff(now)
