"""Envelope de erro da API. Seção 12 do SDD.

Camada de schema (seção 6.2 do SDD). `app.core.errors` monta o envelope a partir dos erros de
domínio e dos erros de validação do FastAPI, e `app.core.middleware` o usa no 403 de origem
inválida e de segredo da borda. Os controladores citam `ErrorResponse` em `responses=`, para o
OpenAPI descrever os erros de cada rota.
"""

from uuid import UUID

from pydantic import BaseModel


# O objeto `error` da seção 12. `code` é estável (`validation_error`, `rate_limited`...),
# `message` é o texto em português e `request_id` liga a resposta aos logs. Os opcionais só
# saem no JSON quando têm valor, porque os tratadores serializam com `exclude_none=True`:
# `retry_after_seconds` no 429, `message_id` no 409 de mensagem repetida e `field_errors`, um
# texto por nome de campo, nos erros de campo.
class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    retry_after_seconds: int | None = None
    message_id: UUID | None = None
    field_errors: dict[str, str] | None = None
    # Do atendimento humano (seção 29.10): os ids do 409 `handoff_active` e o status do 503
    # `handoff_unavailable`.
    handoff_id: UUID | None = None
    conversation_id: UUID | None = None
    availability: str | None = None


# O corpo de toda resposta de erro: `{"error": {...}}`.
class ErrorResponse(BaseModel):
    error: ErrorBody
