"""Pedidos e respostas da conta do membro. Seção 12 do SDD."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProfilePatchRequest(BaseModel):
    """Só os campos enviados mudam. `null` limpa um campo opcional."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    visitor_type: str | None = Field(default=None, max_length=40)
    visit_reason: str | None = Field(default=None, max_length=40)


class ConsentChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    granted: bool


class ConsentItemResponse(BaseModel):
    purpose: str
    document_version: str
    granted_at: datetime
    revoked_at: datetime | None
    source: str


class ConsentStateResponse(BaseModel):
    purpose: str
    granted: bool
    document_version: str | None
    granted_at: datetime | None


class ConsentsResponse(BaseModel):
    current: list[ConsentStateResponse]
    history: list[ConsentItemResponse]


class ExportProfile(BaseModel):
    email: str
    full_name: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None
    role: str
    created_at: datetime


class ExportCitation(BaseModel):
    index: int
    document_title: str
    heading: str | None


class ExportMessage(BaseModel):
    role: str
    content: str
    citations: list[ExportCitation]
    outcome: str | None
    feedback: int | None
    created_at: datetime


class ExportConversation(BaseModel):
    id: UUID
    created_at: datetime
    messages: list[ExportMessage]


class ExportResponse(BaseModel):
    exported_at: datetime
    profile: ExportProfile
    consents: list[ConsentItemResponse]
    conversations: list[ExportConversation]
