"""Tratador único do envelope de erro. Os tipos ficam em app.domain.errors. Seção 6.2."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.core.context import current_request_id
from app.domain.errors import (
    BadOrigin,
    BudgetExceeded,
    Conflict,
    DomainError,
    DuplicateMessage,
    Forbidden,
    NotFound,
    ProviderUnavailable,
    RateLimited,
    Unauthenticated,
    ValidationFailed,
)
from app.prompts.auth import VALIDATION
from app.schemas.errors import ErrorBody, ErrorResponse

_HTTP_STATUS: dict[type[DomainError], int] = {
    NotFound: 404,
    Conflict: 409,
    BadOrigin: 403,
    Forbidden: 403,
    Unauthenticated: 401,
    ValidationFailed: 422,
    RateLimited: 429,
    BudgetExceeded: 503,
    ProviderUnavailable: 503,
}


def status_for(error: DomainError) -> int:
    for error_type, status in _HTTP_STATUS.items():
        if isinstance(error, error_type):
            return status
    return 500


def error_payload(error: DomainError) -> ErrorResponse:
    retry_after_seconds = error.retry_after_seconds if isinstance(error, RateLimited) else None
    message_id = error.message_id if isinstance(error, DuplicateMessage) else None
    return ErrorResponse(
        error=ErrorBody(
            code=error.code,
            message=error.message,
            request_id=current_request_id(),
            retry_after_seconds=retry_after_seconds,
            message_id=message_id,
        )
    )


async def domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        raise exc
    return JSONResponse(
        status_code=status_for(exc),
        content=error_payload(exc).model_dump(exclude_none=True, mode="json"),
    )


async def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    payload = ErrorResponse(
        error=ErrorBody(
            code="validation_error",
            message=VALIDATION,
            request_id=current_request_id(),
        )
    )
    return JSONResponse(status_code=422, content=payload.model_dump(exclude_none=True, mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
