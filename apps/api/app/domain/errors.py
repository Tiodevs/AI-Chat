"""Erros de domínio. O tratador HTTP mora em app.core.errors. Seção 6.2 do SDD."""

from typing import ClassVar
from uuid import UUID


class DomainError(Exception):
    """Base dos erros que o tratador único converte no envelope da seção 12."""

    code: ClassVar[str] = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    code: ClassVar[str] = "not_found"


class Conflict(DomainError):
    code: ClassVar[str] = "conflict"


class DuplicateMessage(Conflict):
    """Reenvio do mesmo client_message_id. O envelope inclui message_id. Seção 7.1."""

    def __init__(self, message: str, *, message_id: UUID) -> None:
        super().__init__(message)
        self.message_id = message_id


class Forbidden(DomainError):
    code: ClassVar[str] = "forbidden"


class BadOrigin(DomainError):
    """Origem diferente de WEB_ORIGIN. HTTP 403, código bad_origin. Seção 10.3."""

    code: ClassVar[str] = "bad_origin"


class Unauthenticated(DomainError):
    code: ClassVar[str] = "unauthenticated"


class ValidationFailed(DomainError):
    code: ClassVar[str] = "validation_error"


class RateLimited(DomainError):
    code: ClassVar[str] = "rate_limited"

    def __init__(self, message: str, *, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class BudgetExceeded(DomainError):
    """Orçamento estourado. O envelope usa o código degraded e HTTP 503."""

    code: ClassVar[str] = "degraded"


class ProviderUnavailable(DomainError):
    code: ClassVar[str] = "provider_unavailable"


class CircuitOpen(ProviderUnavailable):
    """O circuito do modelo está aberto. O pipeline degrada sem chamar o gerador."""
