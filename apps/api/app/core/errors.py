"""Tratador único do envelope de erro. Os tipos ficam em app.domain.errors. Seção 6.2.

Camada de núcleo. Serviços e domínio levantam um `DomainError`, e nenhum controlador monta a
resposta de erro. `register_exception_handlers`, chamado por `create_app`, liga dois
tratadores: o dos erros de domínio e o da validação do FastAPI. Os dois respondem com o
envelope `{"error": {...}}` da seção 12, que leva o `request_id` do pedido.

Ficam fora daqui:

- o 403 do `ApiGuardMiddleware`, que responde antes das rotas e monta o envelope à mão;
- o 404 e o 405 de rota inexistente e o `HTTPException` do `/metrics`, no formato padrão do
  FastAPI, `{"detail": ...}`;
- qualquer outra exceção, que vira o 500 em texto puro do Starlette, sem envelope, sem
  `x-request-id` e sem `Cache-Control: no-store`.
"""

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
    HandoffActive,
    HandoffUnavailable,
    NotFound,
    ProviderUnavailable,
    RateLimited,
    Unauthenticated,
    ValidationFailed,
)
from app.prompts.auth import VALIDATION
from app.schemas.errors import ErrorBody, ErrorResponse

# Status de cada erro (seção 12). `status_for` confere na ordem, com `isinstance`, então uma
# subclasse herda o status da base: `DuplicateMessage` sai 409 e `CircuitOpen`, 503.
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
    HandoffUnavailable: 503,
}


def status_for(error: DomainError) -> int:
    """Status HTTP do erro. Um `DomainError` fora da tabela sai 500, ainda com o envelope."""
    for error_type, status in _HTTP_STATUS.items():
        if isinstance(error, error_type):
            return status
    return 500


def error_payload(error: DomainError) -> ErrorResponse:
    """Monta o envelope da seção 12 para o erro.

    `retry_after_seconds` só entra no 429, `message_id` só no 409 de mensagem repetida, e
    `field_errors` só quando o domínio o preencheu; um dicionário vazio conta como ausente.
    O 409 `handoff_active` leva `handoff_id` e `conversation_id`, e o 503
    `handoff_unavailable` leva `availability` (seção 29.10).
    """
    retry_after_seconds = error.retry_after_seconds if isinstance(error, RateLimited) else None
    message_id = error.message_id if isinstance(error, DuplicateMessage) else None
    active = error if isinstance(error, HandoffActive) else None
    availability = error.availability if isinstance(error, HandoffUnavailable) else None
    return ErrorResponse(
        error=ErrorBody(
            code=error.code,
            message=error.message,
            request_id=current_request_id(),
            retry_after_seconds=retry_after_seconds,
            message_id=message_id,
            field_errors=error.field_errors or None,
            handoff_id=None if active is None else active.handoff_id,
            conversation_id=None if active is None else active.conversation_id,
            availability=availability,
        )
    )


async def domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Responde ao `DomainError` com o status da tabela e o envelope.

    A assinatura recebe `Exception`, como o Starlette pede, e a guarda estreita o tipo: o
    tratador só é registrado para `DomainError`. `exclude_none` tira do JSON os campos
    opcionais ausentes (seção 12), e `mode="json"` converte o UUID de `message_id` em texto.
    """
    if not isinstance(exc, DomainError):
        raise exc
    return JSONResponse(
        status_code=status_for(exc),
        content=error_payload(exc).model_dump(exclude_none=True, mode="json"),
    )


async def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Corpo, query ou caminho fora do schema: 422 `validation_error` (seção 12).

    A mensagem é fixa (`app.prompts.auth.VALIDATION`), e a lista de erros do Pydantic não sai
    na resposta, para não repetir o que a pessoa mandou. Os erros por campo que a interface
    mostra vêm do domínio, em `field_errors`, pelo outro tratador.
    """
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
    """Liga os dois tratadores ao app.

    O `ExceptionMiddleware` do Starlette procura o tratador pela classe da exceção e pelas
    bases dela, então toda subclasse de `DomainError` cai em `domain_error_handler`.
    """
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
