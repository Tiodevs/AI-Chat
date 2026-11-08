"""Métricas lidas do banco: pedidos de titular e execuções da retenção. Seção 18.3 do SDD.

`_scenario` grava quatro pedidos, roda uma regra do `RetentionService` para gravar uma linha
em `retention_runs` e chama `refresh_database_metrics`. O teste troca o `SNAPSHOT` por um novo
nos dois módulos que guardam a referência: o `ops_metrics` importa o nome, e trocar só o de
`app.core.metrics` não chegaria a ele. Destrutivo: apaga todos os `data_subject_requests` e
`retention_runs` do banco antes de gravar, e os pedidos gravados ficam. Precisa de PostgreSQL
com pgvector local (`migrated_database`); sem ele pula, e com `REQUIRE_INTEGRATION_DB=1` falha.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete

from app.core import metrics
from app.core.metrics import DatabaseSnapshot
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.retention import RetentionRule
from app.models.data_subject_request import DataSubjectRequest
from app.models.retention_run import RetentionRun
from app.services.ops_metrics import refresh_database_metrics
from app.services.retention import RetentionService

pytestmark = pytest.mark.integration

NOW = datetime.now(UTC).replace(microsecond=0)


class FrozenClock:
    """Relógio parado em `NOW`, o instante da importação sem microssegundos."""

    def now(self) -> datetime:
        return NOW


def _request(status: str, due_in: timedelta) -> DataSubjectRequest:
    """Pedido de titular com o status e o prazo `due_in` contado de `NOW`."""
    return DataSubjectRequest(
        user_id=None,
        contact_email="titular@example.com",
        request_type="access",
        description="Pedido de teste.",
        status=status,
        received_at=NOW - timedelta(days=1),
        due_at=NOW + due_in,
        closed_at=None if status in ("open", "in_progress") else NOW,
    )


async def _scenario(database_url: str) -> None:
    """Apaga os pedidos e as execuções, grava quatro pedidos, roda uma regra e atualiza.

    Dos três pedidos abertos, um está no prazo e dois atrasados; o quarto está fechado.
    """
    async with open_session(database_url) as session, UnitOfWork(session):
        await session.execute(delete(DataSubjectRequest))
        await session.execute(delete(RetentionRun))
        session.add_all(
            [
                _request("open", timedelta(days=5)),
                _request("in_progress", timedelta(days=-2)),
                _request("open", timedelta(days=-1)),
                _request("done", timedelta(days=-9)),
            ]
        )
    service = RetentionService(database_url=database_url, clock=FrozenClock())
    await service.run_rule(RetentionRule.RATE_LIMIT_WINDOWS)
    await refresh_database_metrics(database_url, FrozenClock())


def test_snapshot_counts_open_and_overdue_requests_and_the_last_run(
    migrated_database: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = DatabaseSnapshot()
    monkeypatch.setattr(metrics, "SNAPSHOT", snapshot)
    monkeypatch.setattr("app.services.ops_metrics.SNAPSHOT", snapshot)

    asyncio.run(_scenario(migrated_database))

    assert snapshot.loaded
    assert (snapshot.dsr_open, snapshot.dsr_overdue) == (1, 2)
    assert "rate_limit_windows" in snapshot.retention_deleted
    assert snapshot.retention_last_run_seconds == NOW.timestamp()
