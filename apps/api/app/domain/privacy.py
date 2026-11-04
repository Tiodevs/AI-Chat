"""Pedidos de titular pelo canal de privacidade. Seções 8.1, 10.4 e 11.5 do SDD."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.domain.auth import (
    RateDecision,
    email_is_valid,
    fixed_window_start,
    normalize_email,
    retry_after_seconds,
)

REQUEST_DUE = timedelta(days=15)
PRIVACY_REQUEST_IP_LIMIT = 5
PRIVACY_REQUEST_WINDOW = timedelta(days=1)
PRIVACY_REQUEST_IP_PURPOSE = "privacy_request_ip"
DESCRIPTION_MAX_CHARS = 2000
CONTACT_EMAIL_MAX_CHARS = 320


class RequestType(StrEnum):
    ACCESS = "access"
    CORRECTION = "correction"
    DELETION = "deletion"
    PORTABILITY = "portability"
    CONSENT_REVOCATION = "consent_revocation"
    INFORMATION_ABOUT_SHARING = "information_about_sharing"
    OBJECTION = "objection"
    OTHER = "other"


class RequestStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    REJECTED = "rejected"


REQUEST_TYPE_CHECK_SQL = (
    "request_type IN (" + ", ".join(f"'{item.value}'" for item in RequestType) + ")"
)
REQUEST_STATUS_CHECK_SQL = (
    "status IN (" + ", ".join(f"'{item.value}'" for item in RequestStatus) + ")"
)


@dataclass(frozen=True, slots=True)
class RequestDraft:
    contact_email: str
    request_type: str
    description: str


def validate_request(
    *, contact_email: str, request_type: str, description: str
) -> tuple[RequestDraft | None, dict[str, str]]:
    """Devolve o rascunho limpo ou os códigos de erro por campo."""
    issues: dict[str, str] = {}
    email = normalize_email(contact_email)
    if not email or len(email) > CONTACT_EMAIL_MAX_CHARS or not email_is_valid(email):
        issues["contact_email"] = "invalid"
    if request_type not in {item.value for item in RequestType}:
        issues["request_type"] = "invalid"
    text = description.strip()
    if not text or len(text) > DESCRIPTION_MAX_CHARS:
        issues["description"] = "invalid"
    if issues:
        return None, issues
    return RequestDraft(contact_email=email, request_type=request_type, description=text), {}


def due_at(received_at: datetime) -> datetime:
    """Prazo de 15 dias corridos a partir do recebimento."""
    return received_at + REQUEST_DUE


def privacy_window_start(now: datetime) -> datetime:
    return fixed_window_start(now, PRIVACY_REQUEST_WINDOW)


def privacy_rate_decision(*, count: int, now: datetime, window_start: datetime) -> RateDecision:
    if count <= PRIVACY_REQUEST_IP_LIMIT:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(
        limited=True,
        retry_after_seconds=retry_after_seconds(now, window_start, PRIVACY_REQUEST_WINDOW),
    )
