"""Atualiza as métricas que vêm do banco. Seção 18.3 do SDD.

Camada de serviço. `controllers/metrics.py` chama `refresh_database_metrics` a cada coleta
de `GET /metrics` (a cada 30 s em produção), antes de renderizar o texto do Prometheus.
Três séries não podem ser contadas no processo da API: `atrium_dsr_open{overdue}`, porque o
pedido de titular fica no banco, e `atrium_retention_deleted{rule}` e
`atrium_retention_last_run_timestamp_seconds`, porque o `retention-job` roda em outro
processo e só deixa a tabela `retention_runs`.

Usa `OpsMetricsRepository` e grava no `SNAPSHOT` de `core/metrics.py`, que o coletor
próprio lê na renderização.
"""

import structlog

from app.core.metrics import SNAPSHOT
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.ports.clock import Clock
from app.repositories.ops_metrics import OpsMetricsRepository


async def refresh_database_metrics(database_url: str, clock: Clock) -> None:
    """Uma falha do banco mantém o último valor e não derruba o /metrics.

    Lê, numa transação curta, os pedidos abertos dentro e fora do prazo, o total apagado por
    regra e a última execução da retenção. Só troca o `SNAPSHOT` depois de ler tudo, então
    a coleta nunca mistura valores novos e antigos. A falha registra
    `metrics.database_refresh_failed` sem detalhe. Sem `DATABASE_URL`, não faz nada.
    """
    if not database_url:
        return
    try:
        async with open_session(database_url) as session, UnitOfWork(session):
            repository = OpsMetricsRepository(session)
            within, overdue = await repository.open_requests(clock.now())
            deleted = await repository.retention_deleted_by_rule()
            last_run = await repository.last_retention_run()
            queued, present = await repository.handoff_counts(clock.now())
    except Exception:
        structlog.get_logger("atrium").warning("metrics.database_refresh_failed")
        return
    SNAPSHOT.dsr_open = within
    SNAPSHOT.dsr_overdue = overdue
    SNAPSHOT.retention_deleted = deleted
    SNAPSHOT.retention_last_run_seconds = last_run.timestamp() if last_run else None
    SNAPSHOT.handoff_queue = queued
    SNAPSHOT.handoff_attendants_available = present
    # Até a primeira leitura bem-sucedida, o coletor não emite estas séries.
    SNAPSHOT.loaded = True
