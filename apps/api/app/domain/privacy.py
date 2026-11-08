"""Pedidos de titular pelo canal de privacidade. Seções 8.1, 10.4, 11.5 e 12 do SDD.

Camada de domínio. `PrivacyRequestService` (`app/services/privacy.py`) valida e grava o pedido
de `POST /v1/privacy/requests`, com prazo e limite por IP; `PrivacyQueueService` monta a fila
do admin e aplica o `PATCH` com `plan_update`; `PrivacyRequestRepository` usa os conjuntos de
status; o modelo `DataSubjectRequest` e a migração `0007_data_subject_requests` usam as
restrições geradas daqui.
"""

import re
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

# Prazo de resposta: 15 dias corridos (seção 11.5).
REQUEST_DUE = timedelta(days=15)
# 5 pedidos por IP por dia (seção 10.4). A janela de um dia começa à meia-noite UTC.
PRIVACY_REQUEST_IP_LIMIT = 5
PRIVACY_REQUEST_WINDOW = timedelta(days=1)
PRIVACY_REQUEST_IP_PURPOSE = "privacy_request_ip"
# Limites do corpo do pedido e da nota do admin (seção 12). 320 caracteres é o teto usual de
# um endereço de e-mail: 64 antes do `@` e 255 depois.
DESCRIPTION_MAX_CHARS = 2000
CONTACT_EMAIL_MAX_CHARS = 320
RESOLUTION_NOTE_MAX_CHARS = 2000
# A fila mostra todos os pedidos abertos e só os mais recentes entre os fechados.
CLOSED_REQUEST_PAGE = 50
# Ação e tipo de alvo gravados em `audit_events` a cada mudança na fila (seção 11.5).
DSR_UPDATE_ACTION = "dsr.update"
DSR_TARGET_TYPE = "data_subject_request"
# O admin responde ao contato por e-mail. Só letras, números e . _ + - antes do @, para um
# endereço como `a@b.com?bcc=c@d.com` ou `a@b.com,c@d.com` não virar cópia num cliente de e-mail.
# Depois do `@`, só letras, números, hífen e ponto entre partes: a seção 12 cita `. _ + -`
# também depois do `@`, e a regra daqui é mais estrita.
_SAFE_CONTACT_EMAIL = re.compile(r"^[a-z0-9._+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+$")
# O PostgreSQL não grava o caractere nulo. Os outros de controle também não têm uso num pedido.
_ALLOWED_CONTROL = frozenset({chr(9), chr(10), chr(13)})  # tab, LF e CR


class RequestType(StrEnum):
    """Tipo do pedido: um por direito do art. 18 da LGPD (seção 11.5), mais `other`."""

    ACCESS = "access"
    CORRECTION = "correction"
    DELETION = "deletion"
    PORTABILITY = "portability"
    CONSENT_REVOCATION = "consent_revocation"
    INFORMATION_ABOUT_SHARING = "information_about_sharing"
    OBJECTION = "objection"
    OTHER = "other"


class RequestStatus(StrEnum):
    """Status do pedido. `open` e `in_progress` estão abertos; `done` e `rejected`, fechados."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    REJECTED = "rejected"


# Restrições CHECK de `data_subject_requests`, geradas dos enums. O modelo e a migração `0007`
# importam estas expressões; um valor novo pede uma migração que troque a restrição.
REQUEST_TYPE_CHECK_SQL = (
    "request_type IN (" + ", ".join(f"'{item.value}'" for item in RequestType) + ")"
)
REQUEST_STATUS_CHECK_SQL = (
    "status IN (" + ", ".join(f"'{item.value}'" for item in RequestStatus) + ")"
)


@dataclass(frozen=True, slots=True)
class RequestDraft:
    """Pedido já limpo: e-mail normalizado e descrição sem os espaços das pontas."""

    contact_email: str
    request_type: str
    description: str


def validate_request(
    *, contact_email: str, request_type: str, description: str
) -> tuple[RequestDraft | None, dict[str, str]]:
    """Devolve o rascunho limpo ou os códigos de erro por campo.

    Confere os três campos e junta todos os erros. Os códigos são todos `invalid`; o serviço
    troca cada um pela mensagem de `field_message`, em `app/prompts/privacy.py`.
    """
    issues: dict[str, str] = {}
    email = normalize_email(contact_email)
    if not email or len(email) > CONTACT_EMAIL_MAX_CHARS or not contact_email_is_safe(email):
        issues["contact_email"] = "invalid"
    if request_type not in {item.value for item in RequestType}:
        issues["request_type"] = "invalid"
    text = description.strip()
    if not text or len(text) > DESCRIPTION_MAX_CHARS or has_control_characters(text):
        issues["description"] = "invalid"
    if issues:
        return None, issues
    return RequestDraft(contact_email=email, request_type=request_type, description=text), {}


def contact_email_is_safe(email: str) -> bool:
    """Um endereço só, sem caractere que um link `mailto:` trate como cabeçalho ou lista.

    A fila do admin transforma o contato em link `mailto:` só quando ele é seguro (seção 15.5).
    """
    return email_is_valid(email) and _SAFE_CONTACT_EMAIL.fullmatch(email) is not None


def has_control_characters(text: str) -> bool:
    """Verdadeiro com caractere de controle (código abaixo de 32) que não é tab, LF nem CR."""
    return any(ord(char) < 32 and char not in _ALLOWED_CONTROL for char in text)


def due_at(received_at: datetime) -> datetime:
    """Prazo de 15 dias corridos a partir do recebimento."""
    return received_at + REQUEST_DUE


def privacy_window_start(now: datetime) -> datetime:
    """Começo da janela de um dia do balde por IP."""
    return fixed_window_start(now, PRIVACY_REQUEST_WINDOW)


def privacy_rate_decision(*, count: int, now: datetime, window_start: datetime) -> RateDecision:
    """Decide o 429 do sexto pedido do mesmo IP no dia. A contagem inclui o pedido atual."""
    if count <= PRIVACY_REQUEST_IP_LIMIT:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(
        limited=True,
        retry_after_seconds=retry_after_seconds(now, window_start, PRIVACY_REQUEST_WINDOW),
    )


# Status abertos e fechados. `PrivacyRequestRepository` lê todos os abertos e os 50 fechados
# mais recentes numa consulta só.
OPEN_STATUSES = frozenset({RequestStatus.OPEN.value, RequestStatus.IN_PROGRESS.value})
CLOSED_STATUSES = frozenset({RequestStatus.DONE.value, RequestStatus.REJECTED.value})


def is_overdue(*, status: str, due_at: datetime, now: datetime) -> bool:
    """Atrasado é o pedido ainda aberto cujo prazo já passou. Fechado nunca atrasa."""
    return status in OPEN_STATUSES and due_at < now


class UpdateProblem(StrEnum):
    """Por que uma mudança de status não pode ser aplicada.

    `closed` vira 409. Os outros viram 422 com `field_errors` em `status` ou em
    `resolution_note`, com as mensagens de `app/prompts/privacy.py`.
    """

    CLOSED = "closed"
    STATUS_INVALID = "status_invalid"
    NOTE_TOO_LONG = "note_too_long"
    NOTE_INVALID = "note_invalid"
    NOTE_REQUIRED = "note_required"


@dataclass(frozen=True, slots=True)
class RequestUpdate:
    """Mudança aprovada por `plan_update`, pronta para gravar.

    `closed_at` só tem valor quando o pedido fecha.
    """

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

    1. Pedido fechado devolve `CLOSED`: se o titular voltar, abre-se um pedido novo.
    2. Status fora da lista devolve `STATUS_INVALID`.
    3. A nota nova é conferida: longa demais ou com caractere de controle é recusada.
    4. Sem nota nova, vale a gravada. Fechar sem nenhuma nota devolve `NOTE_REQUIRED`.
    5. `changed` diz se o status ou a nota mudaram.

    Devolve a mudança ou o problema; nunca os dois.
    """
    # 1.
    if current_status in CLOSED_STATUSES:
        return None, UpdateProblem.CLOSED
    # 2.
    if status not in {item.value for item in RequestStatus}:
        return None, UpdateProblem.STATUS_INVALID
    # 3.
    note = None if resolution_note is None else resolution_note.strip() or None
    if note is not None and len(note) > RESOLUTION_NOTE_MAX_CHARS:
        return None, UpdateProblem.NOTE_TOO_LONG
    if note is not None and has_control_characters(note):
        return None, UpdateProblem.NOTE_INVALID
    # 4.
    final_note = current_note if note is None else note
    closing = status in CLOSED_STATUSES
    if closing and not final_note:
        return None, UpdateProblem.NOTE_REQUIRED
    # 5.
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
    """O motivo gravado em `dsr.update`: só a troca de status, nunca a nota nem o e-mail.

    Por exemplo, `open->in_progress`.
    """
    return f"{previous}->{new}"
