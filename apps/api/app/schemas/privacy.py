"""Canal do titular e fila do admin. Seção 12 do SDD."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PrivacyRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_email: str = Field(max_length=320)
    request_type: str = Field(max_length=40)
    description: str = Field(max_length=4000)


class PrivacyRequestResponse(BaseModel):
    id: UUID
    request_type: str
    status: str
    received_at: datetime
    due_at: datetime


class PrivacyRequestUpdate(BaseModel):
    """Status e nota de resolução. Os limites finos ficam no domínio, com `field_errors`."""

    model_config = ConfigDict(extra="forbid")

    status: str = Field(max_length=40)
    resolution_note: str | None = Field(default=None, max_length=4000)


class PrivacyQueueItemResponse(BaseModel):
    id: UUID
    request_type: str
    status: str
    contact_email: str
    description: str
    received_at: datetime
    due_at: datetime
    closed_at: datetime | None
    resolution_note: str | None
    overdue: bool
    linked_account: bool


class PrivacyQueueResponse(BaseModel):
    generated_at: datetime
    requests: list[PrivacyQueueItemResponse]
