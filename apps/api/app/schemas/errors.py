from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    retry_after_seconds: int | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
