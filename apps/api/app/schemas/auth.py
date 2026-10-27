from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)


class ProfileResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    phone: str | None
    visitor_type: str | None
    visit_reason: str | None
    role: str
    needs_legal_acceptance: bool


class AdminProbeResponse(BaseModel):
    status: str
