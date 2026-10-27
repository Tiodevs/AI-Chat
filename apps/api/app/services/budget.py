"""Orçamento diário no PostgreSQL. Seção 7.1 do SDD."""

import structlog

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.budget import BudgetLevel, budget_level, usage_day
from app.ports.clock import Clock
from app.repositories.token_usage import TokenUsageRepository


class PostgresTokenBudget:
    def __init__(self, database_url: str, clock: Clock, daily_budget: int) -> None:
        self._database_url = database_url
        self._clock = clock
        self._daily_budget = daily_budget

    async def exceeded(self) -> bool:
        if self._daily_budget <= 0:
            return False
        incoming, outgoing = await self._totals()
        level = budget_level(incoming, outgoing, self._daily_budget)
        log_budget(level, (incoming + outgoing) / self._daily_budget)
        return level is BudgetLevel.EXCEEDED

    async def record(self, input_tokens: int, output_tokens: int) -> None:
        if input_tokens < 0 or output_tokens < 0:
            return
        if input_tokens == 0 and output_tokens == 0:
            return
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await TokenUsageRepository(session).add(
                usage_day(self._clock.now()),
                input_tokens,
                output_tokens,
            )

    async def _totals(self) -> tuple[int, int]:
        async with open_session(self._database_url) as session, UnitOfWork(session):
            totals = await TokenUsageRepository(session).totals(usage_day(self._clock.now()))
        return totals


def log_budget(level: BudgetLevel, ratio: float) -> None:
    if level is BudgetLevel.OPEN:
        return
    event = "budget.exceeded" if level is BudgetLevel.EXCEEDED else "budget.warning"
    structlog.get_logger("atrium").warning(event, ratio=round(ratio, 4))
