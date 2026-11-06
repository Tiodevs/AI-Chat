"""Pedidos de titular pelo canal de privacidade. Seções 8.1, 10.4, 11.5 e 12 do SDD."""

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
RESOLUTION_NOTE_MAX_CHARS = 2000
# A fila mostra todos os pedidos abertos e só os mais recentes entre os fechados.
CLOSED_REQUEST_PAGE = 50
DSR_UPDATE_ACTION = "dsr.update"
DSR_TARGET_TYPE = "data_subject_request"


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


OPEN_STATUSES = frozenset({RequestStatus.OPEN.value, RequestStatus.IN_PROGRESS.value})
CLOSED_STATUSES = frozenset({RequestStatus.DONE.value, RequestStatus.REJECTED.value})


def is_overdue(*, status: str, due_at: datetime, now: datetime) -> bool:
    """Atrasado é o pedido ainda aberto cujo prazo já passou. Fechado nunca atrasa."""
    return status in OPEN_STATUSES and due_at < now


class UpdateProblem(StrEnum):
    """Por que uma mudança de status não pode ser aplicada."""

    CLOSED = "closed"
    STATUS_INVALID = "status_invalid"
    NOTE_TOO_LONG = "note_too_long"
    NOTE_REQUIRED = "note_required"


@dataclass(frozen=True, slots=True)
class RequestUpdate:
    status: str
    resolution_note: str | None
    closed_at: datetime | None
    # Sem mudança de status nem de nota, o pedido fica igual e nada vai para a auditoria.
    changed: bool


def plan_update(
    *,
    current_status: str,
    current_note: str | None,
    status: str,
    resolution_note: str | None,
    now: datetime,
) -> tuple[RequestUpdate | None, UpdateProblem | None]:
    """Regras do PATCH do admin. Seções 11.5 e 12 do SDD.

    Um pedido fechado (`done` ou `rejected`) não muda mais. Fechar exige uma nota de
    resolução, nova ou já gravada. Uma nota só com espaços conta como ausente e mantém
    a nota atual.
    """
    if current_status in CLOSED_STATUSES:
        return None, UpdateProblem.CLOSED
    if status not in {item.value for item in RequestStatus}:
        return None, UpdateProblem.STATUS_INVALID
    note = None if resolution_note is None else resolution_note.strip() or None
    if note is not None and len(note) > RESOLUTION_NOTE_MAX_CHARS:
        return None, UpdateProblem.NOTE_TOO_LONG
    final_note = current_note if note is None else note
    closing = status in CLOSED_STATUSES
    if closing and not final_note:
        return None, UpdateProblem.NOTE_REQUIRED
    return (
        RequestUpdate(
            status=status,
            resolution_note=final_note,
            closed_at=now if closing else None,
            changed=status != current_status or final_note != current_note,
        ),
        None,
    )


def transition_reason(previous: str, new: str) -> str:
    """O motivo gravado em `dsr.update`: só a troca de status, nunca a nota nem o e-mail."""
    return f"{previous}->{new}"
