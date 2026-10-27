"""Teto diário de tokens. Seção 7.1 do SDD."""

from datetime import UTC, date, datetime
from enum import StrEnum

WARNING_RATIO = 0.8


class BudgetLevel(StrEnum):
    OPEN = "open"
    WARNING = "warning"
    EXCEEDED = "exceeded"


def usage_day(moment: datetime) -> date:
    """O dia do contador é UTC. Seção 7.1 do SDD."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).date()


def budget_level(input_tokens: int, output_tokens: int, daily_budget: int) -> BudgetLevel:
    """Zero desliga o teto. A partir de 100% degrada. Acima de 80% avisa."""
    if daily_budget <= 0:
        return BudgetLevel.OPEN
    ratio = (input_tokens + output_tokens) / daily_budget
    if ratio >= 1:
        return BudgetLevel.EXCEEDED
    if ratio > WARNING_RATIO:
        return BudgetLevel.WARNING
    return BudgetLevel.OPEN
