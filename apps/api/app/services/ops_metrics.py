"""Atualiza as métricas que vêm do banco. Seção 18.3 do SDD."""

import structlog

from app.core.metrics import SNAPSHOT
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.ports.clock import Clock
from app.repositories.ops_metrics import OpsMetricsRepository


async def refresh_database_metrics(database_url: str, clock: Clock) -> None:
    """Uma falha do banco mantém o último valor e não derruba o /metrics."""
    if not database_url:
        return
    try:
        async with open_session(database_url) as session, UnitOfWork(session):
            repository = OpsMetricsRepository(session)
            within, overdue = await repository.open_requests(clock.now())
            deleted = await repository.retention_deleted_by_rule()
            last_run = await repository.last_retention_run()
    except Exception:
        structlog.get_logger("atrium").warning("metrics.database_refresh_failed")
        return
    SNAPSHOT.dsr_open = within
    SNAPSHOT.dsr_overdue = overdue
    SNAPSHOT.retention_deleted = deleted
    SNAPSHOT.retention_last_run_seconds = last_run.timestamp() if last_run else None
    SNAPSHOT.loaded = True
