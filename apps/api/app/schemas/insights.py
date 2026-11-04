"""Respostas da visão geral, da qualidade e do inspetor. Seção 12 do SDD."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MetricResponse(BaseModel):
    current: float | None
    previous: float | None


class TrendPointResponse(BaseModel):
    date: date
    questions: int
    answered: int


class FunnelRowResponse(BaseModel):
    step: Literal["started", "password_set", "completed"]
    chat: int
    form: int


class BudgetResponse(BaseModel):
    used_tokens: int
    daily_budget: int
    ratio: float


class OverviewResponse(BaseModel):
    period_days: int
    generated_at: datetime
    questions: MetricResponse
    answer_rate: MetricResponse
    abstention_rate: MetricResponse
    helpful_rate: MetricResponse
    trend: list[TrendPointResponse]
    outcomes: dict[str, int]
    intents: dict[str, int]
    feedback: dict[str, int]
    funnel: list[FunnelRowResponse]
    budget: BudgetResponse


class ConversationSummaryResponse(BaseModel):
    id: UUID
    subject_kind: Literal["guest", "member"]
    pseudonym: str
    started_at: datetime
    last_activity_at: datetime
    questions: int
    last_outcome: str | None
    helpful: int
    not_helpful: int


class QualityResponse(BaseModel):
    period_days: int
    outcomes: dict[str, int]
    feedback: dict[str, int]
    conversations: list[ConversationSummaryResponse]


class InspectorCitationResponse(BaseModel):
    index: int
    document_title: str
    heading: str | None


class InspectorMessageResponse(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    outcome: str | None
    prompt_version: str | None
    model: str | None
    request_id: str | None
    latency_ms: int | None
    run_id: UUID | None
    trace_url: str | None
    citations: list[InspectorCitationResponse]
    rating: int | None


class InspectionResponse(BaseModel):
    id: UUID
    subject_kind: Literal["guest", "member"]
    pseudonym: str
    created_at: datetime
    messages: list[InspectorMessageResponse]


class RevealRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(max_length=2000)


class IdentityResponse(BaseModel):
    conversation_id: UUID
    full_name: str
    email: str
