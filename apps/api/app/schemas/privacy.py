"""Pedido do canal do titular. Seção 12 do SDD."""

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
