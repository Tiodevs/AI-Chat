"""Pedidos e respostas do cadastro. Seção 12 do SDD."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.registration import MAX_MESSAGE_CHARS


class RegistrationMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped or len(stripped) > MAX_MESSAGE_CHARS:
            raise ValueError("invalid registration message")
        return stripped


class PasswordRequest(BaseModel):
    """A senha só entra por este pedido ou pelo formulário. Não vai para o modelo."""

    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=200)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept: bool


class AcceptanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept_terms: bool
    document_version: str = Field(min_length=1, max_length=64)
    age_18_plus: bool
    profile_personalization: bool = False
    quality_improvement: bool = False


class FormRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID | None = None
    full_name: str = Field(max_length=200)
    email: str = Field(max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    visitor_type: str | None = Field(default=None, max_length=40)
    visit_reason: str | None = Field(default=None, max_length=40)
    password: str = Field(min_length=1, max_length=200)
    accept_terms: bool
    document_version: str = Field(min_length=1, max_length=64)
    age_18_plus: bool
    profile_personalization: bool = False
    quality_improvement: bool = False


class FieldsPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    visitor_type: str | None = None
    visit_reason: str | None = None


class RegistrationFieldsResponse(BaseModel):
    full_name: str | None
    email: str | None
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None


class TranscriptMessageResponse(BaseModel):
    """Serializador da transcrição. Não tem campo de senha."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    text: str
    created_at: datetime


class RegistrationSessionResponse(BaseModel):
    id: UUID
    status: str
    path: Literal["chat", "form"]
    fields: RegistrationFieldsResponse
    field_errors: dict[str, str]
    next_step: str
    prompt: str
    messages: list[TranscriptMessageResponse]
    expires_at: datetime
