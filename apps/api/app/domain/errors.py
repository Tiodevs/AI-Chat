"""Erros de domínio. O tratador HTTP mora em app.core.errors. Seção 6.2 do SDD."""

from typing import ClassVar


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


class Forbidden(DomainError):
    code: ClassVar[str] = "forbidden"


class Unauthenticated(DomainError):
    code: ClassVar[str] = "unauthenticated"


class ValidationFailed(DomainError):
    code: ClassVar[str] = "validation_error"


class RateLimited(DomainError):
    code: ClassVar[str] = "rate_limited"


class BudgetExceeded(DomainError):
    """Orçamento estourado. O envelope usa o código degraded e HTTP 503."""

    code: ClassVar[str] = "degraded"


class ProviderUnavailable(DomainError):
    code: ClassVar[str] = "provider_unavailable"
