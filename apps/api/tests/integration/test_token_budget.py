"""`token_usage_days` soma o dia UTC e não vaza para outro dia. NFR-13, seções 7.1 e 8.1.

Grava pelo `TokenUsageRepository` e confere o `PostgresTokenBudget` com o relógio `_FixedClock`
em dias de 1999, que nenhum outro teste usa, e apaga as duas linhas no fim. Precisa de
PostgreSQL com pgvector local (`migrated_database`); sem ele pula, e com
`REQUIRE_INTEGRATION_DB=1` falha.
"""

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.repositories.token_usage import TokenUsageRepository
from app.services.budget import PostgresTokenBudget

pytestmark = pytest.mark.integration

_DAY = datetime(1999, 12, 31, tzinfo=UTC)
_OTHER = datetime(1999, 12, 30, tzinfo=UTC)


def test_daily_token_counter_accumulates_and_degrades_at_the_budget(
    migrated_database: str,
) -> None:
    asyncio.run(_exercise(migrated_database))


async def _exercise(database_url: str) -> None:
    """Soma tokens no dia `_DAY` e confere o teto do `PostgresTokenBudget`.

    O uso de 13 iguala o teto de 13 e estoura; 14 tem folga; 0 desliga o teto; e o outro dia
    começa vazio (seção 7.1). No fim, apaga as duas linhas de 1999.
    """
    try:
        async with open_session(database_url) as session, UnitOfWork(session):
            await TokenUsageRepository(session).add(_DAY.date(), 4, 6)
        async with open_session(database_url) as session, UnitOfWork(session):
            await TokenUsageRepository(session).add(_DAY.date(), 1, 2)
        async with open_session(database_url) as session, UnitOfWork(session):
            repository = TokenUsageRepository(session)
            assert await repository.totals(_DAY.date()) == (5, 8)
            assert await repository.totals(_OTHER.date()) == (0, 0)

        full = PostgresTokenBudget(database_url, _FixedClock(_DAY), daily_budget=13)
        room = PostgresTokenBudget(database_url, _FixedClock(_DAY), daily_budget=14)
        disabled = PostgresTokenBudget(database_url, _FixedClock(_DAY), daily_budget=0)
        other_day = PostgresTokenBudget(database_url, _FixedClock(_OTHER), daily_budget=1)
        assert await full.exceeded() is True
        assert await room.exceeded() is False
        assert await disabled.exceeded() is False
        assert await other_day.exceeded() is False

        await room.record(1, 1)
        async with open_session(database_url) as session, UnitOfWork(session):
            assert await TokenUsageRepository(session).totals(_DAY.date()) == (6, 9)
    finally:
        async with open_session(database_url) as session, UnitOfWork(session):
            await session.execute(
                text("DELETE FROM token_usage_days WHERE day IN (:day, :other)"),
                {"day": _DAY.date(), "other": _OTHER.date()},
            )


class _FixedClock:
    """Relógio parado no instante dado."""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment
