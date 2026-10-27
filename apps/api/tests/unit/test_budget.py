"""Teto diário. Zero desliga. A partir de 100% degrada. Seção 7.1."""

import asyncio
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.logging import configure_logging
from app.domain.budget import BudgetLevel, budget_level, usage_day
from app.domain.outcomes import Outcome
from app.prompts.qa import UNAVAILABLE
from app.services.budget import PostgresTokenBudget, log_budget
from app.services.question import QuestionService
from app.workflows.qa import ConversationTurn, QaResult

_PLUS_THREE = timezone(timedelta(hours=3))


def test_budget_warns_only_above_80_percent_and_degrades_at_100() -> None:
    assert budget_level(80, 0, 100) is BudgetLevel.OPEN
    assert budget_level(81, 0, 100) is BudgetLevel.WARNING
    assert budget_level(50, 50, 100) is BudgetLevel.EXCEEDED
    assert budget_level(100, 1, 100) is BudgetLevel.EXCEEDED
    assert budget_level(1000, 0, 0) is BudgetLevel.OPEN
    assert budget_level(10, 0, -1) is BudgetLevel.OPEN


def test_usage_day_is_utc() -> None:
    assert usage_day(datetime(1999, 12, 31, 23, 30, tzinfo=UTC)) == datetime(1999, 12, 31).date()
    assert usage_day(datetime(2000, 1, 1, 2, tzinfo=_PLUS_THREE)) == datetime(1999, 12, 31).date()
    assert usage_day(datetime(1999, 12, 31, 23, 30)) == datetime(1999, 12, 31).date()


def test_zero_budget_does_not_open_the_database() -> None:
    budget = PostgresTokenBudget("postgresql+asyncpg://127.0.0.1:1/none", _Clock(), 0)

    async def check() -> None:
        assert await budget.exceeded() is False
        await budget.record(0, 0)

    asyncio.run(check())


def test_open_budget_does_not_log(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    log_budget(BudgetLevel.OPEN, 0.5)
    assert _events(capsys) == []


def test_warning_and_exceeded_log_the_ratio(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    log_budget(BudgetLevel.WARNING, 0.81)
    log_budget(BudgetLevel.EXCEEDED, 1)
    events = _events(capsys)
    assert [event["event"] for event in events] == ["budget.warning", "budget.exceeded"]
    assert [event["ratio"] for event in events] == [0.81, 1.0]


def test_exceeded_budget_returns_degraded_without_calling_the_generator() -> None:
    workflow = _Workflow()
    service = QuestionService(workflow, _MemoryBudget(exceeded=True))
    result = asyncio.run(service.ask("Qual é o horário?"))
    assert workflow.calls == 0
    assert result.outcome is Outcome.DEGRADED
    assert result.text == UNAVAILABLE
    assert result.input_tokens == 0
    assert result.output_tokens == 0


def test_open_budget_records_the_workflow_tokens() -> None:
    workflow = _Workflow()
    budget = _MemoryBudget(exceeded=False)
    service = QuestionService(workflow, budget)
    result = asyncio.run(service.ask("Qual é o horário?", request_id="req-1"))
    assert workflow.calls == 1
    assert workflow.request_ids == ["req-1"]
    assert result.outcome is Outcome.ANSWERED
    assert budget.recorded == [(3, 4)]


class _Clock:
    def now(self) -> datetime:
        return datetime(2026, 10, 27, tzinfo=UTC)


class _MemoryBudget:
    def __init__(self, *, exceeded: bool) -> None:
        self._exceeded = exceeded
        self.recorded: list[tuple[int, int]] = []

    async def exceeded(self) -> bool:
        return self._exceeded

    async def record(self, input_tokens: int, output_tokens: int) -> None:
        self.recorded.append((input_tokens, output_tokens))


class _Workflow:
    def __init__(self) -> None:
        self.calls = 0
        self.request_ids: list[str] = []

    async def run(
        self,
        question: str,
        *,
        history: Sequence[ConversationTurn],
        visitor_type: str | None,
        request_id: str,
    ) -> QaResult:
        del question, history, visitor_type
        self.calls += 1
        self.request_ids.append(request_id)
        return QaResult(
            outcome=Outcome.ANSWERED,
            text="11:00 [1].",
            citations=(),
            input_tokens=3,
            output_tokens=4,
            model="fake-chat",
            prompt_version="qa-generate@2026-10-27.1",
            intent="public_info",
            confidence=0.9,
            standalone_question="Horário de visita",
            run_id=uuid4(),
        )


def _events(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    output = capsys.readouterr().out
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]
