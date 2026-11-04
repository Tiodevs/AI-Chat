"""Visão geral, qualidade, inspetor e revelação de identidade do admin.

Seções 11.8, 12, 15.5 e 18.3 do SDD. Abrir uma conversa grava `conversation.view`.
Revelar exige motivo e grava `identity.reveal` (FR-15).
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.errors import Conflict, NotFound, ValidationFailed
from app.domain.insights import (
    FeedbackFilter,
    InsightAction,
    abstentions,
    budget_ratio,
    clean_reason,
    days_of,
    intent_counts,
    rate,
    short_pseudonym,
    trace_url,
    valid_period,
    windows_for,
)
from app.domain.outcomes import Outcome
from app.domain.pseudonym import subject_pseudonym
from app.ports.clock import Clock
from app.prompts.conversations import CONVERSATION_NOT_FOUND
from app.prompts.insights import (
    CONVERSATION_HIDDEN,
    FILTER_INVALID,
    GUEST_HAS_NO_IDENTITY,
    PERIOD_INVALID,
    REASON_INVALID,
)
from app.repositories.audit import AuditRepository
from app.repositories.insights import ConversationOwner, InsightsRepository

TARGET_TYPE = "conversation"


@dataclass(frozen=True, slots=True)
class Metric:
    current: float | None
    previous: float | None


@dataclass(frozen=True, slots=True)
class TrendPoint:
    day: date
    questions: int
    answered: int


@dataclass(frozen=True, slots=True)
class FunnelRow:
    step: str
    chat: int
    form: int


@dataclass(frozen=True, slots=True)
class Budget:
    used_tokens: int
    daily_budget: int
    ratio: float


@dataclass(frozen=True, slots=True)
class Overview:
    period_days: int
    generated_at: datetime
    questions: Metric
    answer_rate: Metric
    abstention_rate: Metric
    helpful_rate: Metric
    trend: list[TrendPoint]
    outcomes: dict[str, int]
    intents: dict[str, int]
    feedback: dict[str, int]
    funnel: list[FunnelRow]
    budget: Budget


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    id: UUID
    subject_kind: str
    pseudonym: str
    started_at: datetime
    last_activity_at: datetime
    questions: int
    last_outcome: str | None
    helpful: int
    not_helpful: int


@dataclass(frozen=True, slots=True)
class Quality:
    period_days: int
    outcomes: dict[str, int]
    feedback: dict[str, int]
    conversations: list[ConversationSummary]


@dataclass(frozen=True, slots=True)
class InspectorMessage:
    id: UUID
    role: str
    content: str
    created_at: datetime
    outcome: str | None
    prompt_version: str | None
    model: str | None
    request_id: str | None
    latency_ms: int | None
    run_id: UUID | None
    trace_url: str | None
    citations: list[dict[str, Any]]
    rating: int | None


@dataclass(frozen=True, slots=True)
class Inspection:
    id: UUID
    subject_kind: str
    pseudonym: str
    created_at: datetime
    messages: list[InspectorMessage]


@dataclass(frozen=True, slots=True)
class Identity:
    conversation_id: UUID
    full_name: str
    email: str


class InsightsService:
    def __init__(
        self,
        *,
        database_url: str,
        clock: Clock,
        pseudonym_key: str,
        daily_budget: int,
        run_url_template: str,
    ) -> None:
        self._database_url = database_url
        self._clock = clock
        self._pseudonym_key = pseudonym_key
        self._daily_budget = daily_budget
        self._run_url_template = run_url_template

    async def overview(self, period_days: int) -> Overview:
        _check_period(period_days)
        now = self._clock.now()
        windows = windows_for(now, period_days)
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = InsightsRepository(session)
            questions = await repository.question_count(windows.current)
            previous_questions = await repository.question_count(windows.previous)
            outcomes = await repository.outcome_counts(windows.current)
            previous_outcomes = await repository.outcome_counts(windows.previous)
            ratings = await repository.feedback_counts(windows.current)
            previous_ratings = await repository.feedback_counts(windows.previous)
            daily = await repository.daily(windows.current)
            funnel = await repository.funnel(windows.current)
            used = await repository.tokens_on(now.date())
        return Overview(
            period_days=period_days,
            generated_at=now,
            questions=Metric(float(questions), float(previous_questions)),
            answer_rate=Metric(_answer_rate(outcomes), _answer_rate(previous_outcomes)),
            abstention_rate=Metric(
                _abstention_rate(outcomes), _abstention_rate(previous_outcomes)
            ),
            helpful_rate=Metric(_helpful_rate(ratings), _helpful_rate(previous_ratings)),
            trend=[
                TrendPoint(day, *daily.get(day, (0, 0))) for day in days_of(windows.current)
            ],
            outcomes={item.value: outcomes.get(item.value, 0) for item in Outcome},
            intents=intent_counts(outcomes),
            feedback=_feedback(ratings, sum(outcomes.values())),
            funnel=[FunnelRow(step, row["chat"], row["form"]) for step, row in funnel.items()],
            budget=Budget(used, self._daily_budget, budget_ratio(used, self._daily_budget)),
        )

    async def quality(
        self, *, period_days: int, outcome: str | None, feedback: str | None
    ) -> Quality:
        _check_period(period_days)
        if outcome is not None and outcome not in {item.value for item in Outcome}:
            raise ValidationFailed(FILTER_INVALID, field_errors={"outcome": FILTER_INVALID})
        if feedback is not None and feedback not in {item.value for item in FeedbackFilter}:
            raise ValidationFailed(FILTER_INVALID, field_errors={"feedback": FILTER_INVALID})
        window = windows_for(self._clock.now(), period_days).current
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = InsightsRepository(session)
            outcomes = await repository.outcome_counts(window)
            ratings = await repository.feedback_counts(window)
            rows = await repository.conversations(
                window,
                outcome=outcome,
                feedback=None if feedback is None else FeedbackFilter(feedback),
            )
        return Quality(
            period_days=period_days,
            outcomes={item.value: outcomes.get(item.value, 0) for item in Outcome},
            feedback=_feedback(ratings, sum(outcomes.values())),
            conversations=[
                ConversationSummary(
                    id=row.id,
                    subject_kind=_kind(row.user_id),
                    pseudonym=self._pseudonym(row.user_id, row.guest_key_id),
                    started_at=row.created_at,
                    last_activity_at=row.last_activity_at,
                    questions=row.questions,
                    last_outcome=row.last_outcome,
                    helpful=row.helpful,
                    not_helpful=row.not_helpful,
                )
                for row in rows
            ],
        )

    async def inspect(self, *, admin_id: UUID, conversation_id: UUID) -> Inspection:
        """Abre a conversa no inspetor e grava `conversation.view` na mesma transação."""
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = InsightsRepository(session)
            owner = await _eligible_owner(repository, conversation_id)
            messages = await repository.messages(conversation_id)
            await AuditRepository(session).record(
                actor_user_id=admin_id,
                action=InsightAction.CONVERSATION_VIEW.value,
                target_type=TARGET_TYPE,
                target_id=conversation_id,
                created_at=self._clock.now(),
            )
        return Inspection(
            id=owner.id,
            subject_kind=_kind(owner.user_id),
            pseudonym=self._pseudonym(owner.user_id, owner.guest_key_id),
            created_at=owner.created_at,
            messages=[
                InspectorMessage(
                    id=message.id,
                    role=message.role,
                    content=message.content,
                    created_at=message.created_at,
                    outcome=message.outcome,
                    prompt_version=message.prompt_version,
                    model=message.model,
                    request_id=message.request_id,
                    latency_ms=message.latency_ms,
                    run_id=message.langsmith_run_id,
                    trace_url=trace_url(self._run_url_template, message.langsmith_run_id),
                    citations=[_citation(item) for item in message.citations],
                    rating=message.rating,
                )
                for message in messages
            ],
        )

    async def reveal(self, *, admin_id: UUID, conversation_id: UUID, reason: str) -> Identity:
        """Devolve nome e e-mail do membro e grava `identity.reveal` com o motivo (FR-15)."""
        clean = clean_reason(reason)
        if clean is None:
            raise ValidationFailed(REASON_INVALID, field_errors={"reason": REASON_INVALID})
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = InsightsRepository(session)
            owner = await _eligible_owner(repository, conversation_id)
            if owner.user_id is None:
                raise Conflict(GUEST_HAS_NO_IDENTITY)
            identity = await repository.identity(owner.user_id)
            if identity is None:
                raise NotFound(CONVERSATION_NOT_FOUND)
            revealed = Identity(
                conversation_id=conversation_id, full_name=identity[0], email=identity[1]
            )
            await AuditRepository(session).record(
                actor_user_id=admin_id,
                action=InsightAction.IDENTITY_REVEAL.value,
                target_type=TARGET_TYPE,
                target_id=conversation_id,
                reason=clean,
                created_at=self._clock.now(),
            )
        return revealed

    def _pseudonym(self, user_id: UUID | None, guest_key_id: UUID | None) -> str:
        subject = user_id or guest_key_id
        if subject is None:
            return ""
        return short_pseudonym(subject_pseudonym(subject, self._pseudonym_key))


async def _eligible_owner(
    repository: InsightsRepository, conversation_id: UUID
) -> ConversationOwner:
    owner = await repository.owner(conversation_id)
    if owner is None:
        raise NotFound(CONVERSATION_NOT_FOUND)
    if not owner.eligible:
        # Sem o consentimento de melhoria, a conversa fica só nos agregados (11.8).
        raise NotFound(CONVERSATION_HIDDEN)
    return owner


def _check_period(period_days: int) -> None:
    if not valid_period(period_days):
        raise ValidationFailed(PERIOD_INVALID, field_errors={"period_days": PERIOD_INVALID})


def _kind(user_id: UUID | None) -> str:
    return "guest" if user_id is None else "member"


def _answer_rate(outcomes: dict[str, int]) -> float | None:
    return rate(outcomes.get(Outcome.ANSWERED.value, 0), sum(outcomes.values()))


def _abstention_rate(outcomes: dict[str, int]) -> float | None:
    return rate(abstentions(outcomes), sum(outcomes.values()))


def _helpful_rate(ratings: dict[int, int]) -> float | None:
    return rate(ratings.get(1, 0), ratings.get(1, 0) + ratings.get(-1, 0))


def _feedback(ratings: dict[int, int], answers: int) -> dict[str, int]:
    helpful = ratings.get(1, 0)
    not_helpful = ratings.get(-1, 0)
    return {
        FeedbackFilter.HELPFUL.value: helpful,
        FeedbackFilter.NOT_HELPFUL.value: not_helpful,
        FeedbackFilter.NONE.value: max(0, answers - helpful - not_helpful),
    }


def _citation(item: object) -> dict[str, Any]:
    """Só índice, título e seção. O id do chunk não sai para a tela."""
    if not isinstance(item, dict):
        return {"index": 0, "document_title": "", "heading": None}
    heading = item.get("heading")
    return {
        "index": int(item.get("index", 0)),
        "document_title": str(item.get("document_title", "")),
        "heading": None if heading is None else str(heading),
    }
