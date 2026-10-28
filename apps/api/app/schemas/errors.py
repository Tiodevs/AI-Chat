from uuid import UUID

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    retry_after_seconds: int | None = None
    message_id: UUID | None = None
    field_errors: dict[str, str] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
