"""Regras da visão geral e da qualidade do admin. Seções 11.8, 12, 15.5 e 16.3 do SDD."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from app.domain.outcomes import Outcome

PERIOD_DAYS = (7, 30)
DEFAULT_PERIOD_DAYS = 7
PSEUDONYM_CHARS = 8
REVEAL_REASON_MIN_CHARS = 10
REVEAL_REASON_MAX_CHARS = 500
CONVERSATION_PAGE = 50
RUN_ID_PLACEHOLDER = "{run_id}"


class InsightAction(StrEnum):
    CONVERSATION_VIEW = "conversation.view"
    IDENTITY_REVEAL = "identity.reveal"


class Intent(StrEnum):
    """Intenção derivada do desfecho gravado. A mensagem não guarda a intenção."""

    PUBLIC_INFO = "public_info"
    MEDICAL_ADVICE = "medical_advice"
    OFF_TOPIC = "off_topic"


class FeedbackFilter(StrEnum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"
    NONE = "none"


class FunnelStep(StrEnum):
    STARTED = "started"
    PASSWORD_SET = "password_set"
    COMPLETED = "completed"


ABSTENTION_OUTCOMES = frozenset({Outcome.ABSTAINED.value, Outcome.GROUNDING_FAILED.value})


@dataclass(frozen=True, slots=True)
class Window:
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class Windows:
    current: Window
    previous: Window


def valid_period(days: int) -> bool:
    return days in PERIOD_DAYS


def windows_for(now: datetime, days: int) -> Windows:
    """Período atual termina agora. O anterior tem o mesmo tamanho, logo antes."""
    size = timedelta(days=days)
    start = now - size
    return Windows(current=Window(start, now), previous=Window(start - size, start))


def days_of(window: Window) -> list[date]:
    """Dias UTC que o período toca, do mais antigo ao mais novo."""
    first = window.start.date()
    last = window.end.date()
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def intent_for(outcome: str) -> Intent:
    if outcome == Outcome.REFUSED.value:
        return Intent.MEDICAL_ADVICE
    if outcome == Outcome.OFF_TOPIC.value:
        return Intent.OFF_TOPIC
    return Intent.PUBLIC_INFO


def intent_counts(outcomes: dict[str, int]) -> dict[str, int]:
    totals = {item.value: 0 for item in Intent}
    for outcome, count in outcomes.items():
        totals[intent_for(outcome).value] += count
    return totals


def abstentions(outcomes: dict[str, int]) -> int:
    return sum(count for outcome, count in outcomes.items() if outcome in ABSTENTION_OUTCOMES)


def short_pseudonym(full: str) -> str:
    return full[:PSEUDONYM_CHARS]


def clean_reason(reason: str) -> str | None:
    value = " ".join(reason.split())
    if not REVEAL_REASON_MIN_CHARS <= len(value) <= REVEAL_REASON_MAX_CHARS:
        return None
    return value


def trace_url(template: str, run_id: UUID | None) -> str | None:
    """Link do rastro no LangSmith. Sem modelo configurado, o inspetor mostra só o id."""
    if run_id is None or RUN_ID_PLACEHOLDER not in template:
        return None
    return template.replace(RUN_ID_PLACEHOLDER, str(run_id))


def budget_ratio(used: int, budget: int) -> float:
    if budget <= 0:
        return 0.0
    return used / budget
