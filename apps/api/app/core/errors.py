"""Tratador único do envelope de erro. Os tipos ficam em app.domain.errors. Seção 6.2."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.core.context import current_request_id
from app.domain.errors import (
    BudgetExceeded,
    Conflict,
    DomainError,
    Forbidden,
    NotFound,
    ProviderUnavailable,
    RateLimited,
    Unauthenticated,
    ValidationFailed,
)
from app.schemas.errors import ErrorBody, ErrorResponse

_HTTP_STATUS: dict[type[DomainError], int] = {
    NotFound: 404,
    Conflict: 409,
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


async def domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        raise exc
    payload = ErrorResponse(
        error=ErrorBody(
            code=exc.code,
            message=exc.message,
            request_id=current_request_id(),
        )
    )
    return JSONResponse(status_code=status_for(exc), content=payload.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
