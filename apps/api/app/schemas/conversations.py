"""Pedidos e respostas das conversas. Seção 12 do SDD."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.questions import MAX_QUESTION_CHARS


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    client_message_id: UUID

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped or len(stripped) > MAX_QUESTION_CHARS:
            raise ValueError("invalid question length")
        return stripped


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: Literal[-1, 1]


class ConversationCreatedResponse(BaseModel):
    id: UUID
    created_at: datetime


class ConversationSummaryResponse(BaseModel):
    id: UUID
    created_at: datetime


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummaryResponse]


class CitationResponse(BaseModel):
    index: int
    document_title: str
    heading: str | None
    chunk_id: UUID


class MessageResponse(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    client_message_id: UUID | None
    citations: list[CitationResponse]
    outcome: str | None
    created_at: datetime


class ConversationResponse(BaseModel):
    id: UUID
    created_at: datetime
    messages: list[MessageResponse]


class FeedbackResponse(BaseModel):
    message_id: UUID
    rating: Literal[-1, 1]
