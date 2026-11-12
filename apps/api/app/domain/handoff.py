"""Regras puras do atendimento humano: estados, oferta, fila e constantes. Seção 29 do SDD.

Camada de domínio (seção 6.2). Só a biblioteca padrão e os erros de `app.domain.errors`.
Quem usa: `services/handoff.py` (o lado do visitante), `services/attendance.py` (o lado da
equipe), `services/handoff_sweep.py` (a varredura do `lifespan`), `repositories/handoffs.py`,
os modelos e a migração `0010_handoffs`, que geram as restrições CHECK destes enums.

A máquina de estados segue o diagrama da seção 29.5, como a do cadastro (seção 7.2): uma
transição fora dele levanta `Conflict`. As constantes são as da seção 29.14.
"""

import hashlib
import hmac
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from app.domain.errors import Conflict


class HandoffStatus(StrEnum):
    """Estado do atendimento (seção 29.5). Um atendimento `closed` não volta."""

    QUEUED = "queued"
    ASSIGNED = "assigned"
    CLOSED = "closed"


class HandoffTrigger(StrEnum):
    """O desfecho que motivou a oferta (seção 29.4). Vai para `handoffs.trigger`."""

    ABSTAINED = "abstained"
    GROUNDING_FAILED = "grounding_failed"
    OFF_TOPIC = "off_topic"
    DEGRADED = "degraded"
    ERROR = "error"
    NOT_HELPFUL = "not_helpful"


class CloseReason(StrEnum):
    """Motivo do encerramento (seção 29.5): da equipe, do visitante ou da varredura."""

    RESOLVED = "resolved"
    REDIRECTED = "redirected"
    OUT_OF_SCOPE = "out_of_scope"
    NO_RESPONSE = "no_response"
    ABUSIVE = "abusive"
    VISITOR_CANCELLED = "visitor_cancelled"
    VISITOR_ENDED = "visitor_ended"
    QUEUE_TIMEOUT = "queue_timeout"
    VISITOR_LEFT = "visitor_left"
    SERVICE_CLOSED = "service_closed"
    INACTIVITY = "inactivity"


# A lista fechada que a equipe escolhe ao encerrar. Sem nota livre: nenhuma opinião sobre o
# visitante vira dado novo (seção 29.5).
ATTENDANT_CLOSE_REASONS = frozenset(
    {
        CloseReason.RESOLVED,
        CloseReason.REDIRECTED,
        CloseReason.OUT_OF_SCOPE,
        CloseReason.NO_RESPONSE,
        CloseReason.ABUSIVE,
    }
)


class Availability(StrEnum):
    """O status único de `GET /v1/handoff/availability` (seção 29.4)."""

    OPEN = "open"
    BUSY = "busy"
    CLOSED = "closed"
    DISABLED = "disabled"


class PresenceStatus(StrEnum):
    """O que a pessoa da equipe marca no `PresenceToggle` (seção 29.11)."""

    AVAILABLE = "available"
    AWAY = "away"


class RedactionCategory(StrEnum):
    """Por que o texto de uma mensagem foi trocado pelo marcador (seções 29.7 e 29.9.6).

    `retention` é só da regra `handoff_content` (seção 29.9.9); a equipe escolhe uma das
    outras cinco em `REDACT_CATEGORIES`.
    """

    HEALTH = "health"
    DOCUMENT = "document"
    CONTACT = "contact"
    THIRD_PARTY = "third_party"
    OTHER = "other"
    RETENTION = "retention"


REDACT_CATEGORIES = frozenset(category for category in RedactionCategory if category != "retention")


class NoticeKind(StrEnum):
    """O `kind` da carga do `NOTIFY` (seção 29.6 e ADR-016)."""

    QUEUE = "queue"
    STATUS = "status"
    MESSAGE = "message"
    REMOVED = "removed"


# Constantes da seção 29.14.
MAX_QUEUE = 20
QUEUE_TIMEOUT = timedelta(minutes=15)
VISITOR_ABSENT = timedelta(minutes=5)
ASSIGNED_IDLE = timedelta(minutes=30)
PRESENCE_WINDOW = timedelta(seconds=45)
ATTENDANT_GONE = timedelta(minutes=2)
MAX_PER_ATTENDANT = 3
SWEEP_INTERVAL_SECONDS = 30.0
STREAM_TICK_SECONDS = 15.0
STREAM_MAX_SECONDS = 600.0
ABUSE_BLOCK = timedelta(hours=24)
MAX_VISITOR_CHARS = 1000
MAX_STAFF_CHARS = 2000
CONTENT_RETENTION = timedelta(days=90)
# Os 8 caracteres do HMAC no rótulo do atendimento (seção 29.9.4).
LABEL_CHARS = 8

# Limites dos fluxos da seção 29.6. Os contadores são do processo.
MAX_STREAMS_PER_CONVERSATION = 3
MAX_STREAMS_PER_ATTENDANT = 2
MAX_STREAMS_PER_PROCESS = 300

# Baldes da seção 29.8, todos por hora.
HANDOFF_WINDOW = timedelta(hours=1)
REQUEST_SUBJECT_LIMIT = 3
REQUEST_IP_LIMIT = 10
VISITOR_MESSAGE_LIMIT = 120
STAFF_MESSAGE_LIMIT = 600
REQUEST_SUBJECT_PURPOSE = "handoff_subject"
REQUEST_IP_PURPOSE = "handoff_ip"
VISITOR_MESSAGE_PURPOSE = "handoff_visitor_message"
STAFF_MESSAGE_PURPOSE = "handoff_staff_message"

# O canal do `LISTEN/NOTIFY` (ADR-016).
NOTIFY_CHANNEL = "atrium_handoff"

# O que fica gravado no lugar do texto. A remoção pela equipe mostra ao visitante a frase da
# seção 29.9.6, escolhida pela `redaction`; a retenção mostra este marcador (seção 29.9.9).
REDACTED_MARKER = "[mensagem removida]"
RETENTION_MARKER = "[conteúdo do atendimento apagado]"

# As transições do diagrama da seção 29.5. `closed` não sai para lugar nenhum.
_TRANSITIONS = frozenset(
    {
        (HandoffStatus.QUEUED, HandoffStatus.ASSIGNED),
        (HandoffStatus.ASSIGNED, HandoffStatus.QUEUED),
        (HandoffStatus.QUEUED, HandoffStatus.CLOSED),
        (HandoffStatus.ASSIGNED, HandoffStatus.CLOSED),
    }
)

# Desfechos que oferecem o atendimento logo depois da resposta (seção 29.4). `answered` só
# oferece com a nota não útil, e `refused` e `cancelled` nunca oferecem.
_OFFER_BY_OUTCOME = {
    "abstained": HandoffTrigger.ABSTAINED,
    "grounding_failed": HandoffTrigger.GROUNDING_FAILED,
    "off_topic": HandoffTrigger.OFF_TOPIC,
    "degraded": HandoffTrigger.DEGRADED,
    "error": HandoffTrigger.ERROR,
}


def check_sql(column: str, values: Iterable[StrEnum]) -> str:
    """A restrição CHECK de uma coluna de enum, como `status IN ('queued', ...)`."""
    return f"{column} IN (" + ", ".join(f"'{item.value}'" for item in values) + ")"


def transition(current: str, target: HandoffStatus, *, conflict_message: str) -> HandoffStatus:
    """Confere a transição do diagrama da seção 29.5 e devolve o estado novo.

    `conflict_message` é o texto em português de `app/prompts/handoff.py`, que o domínio não
    importa. Uma transição fora do diagrama, inclusive qualquer saída de `closed`, levanta
    `Conflict`, e o serviço não grava nada.
    """
    if (HandoffStatus(current), target) not in _TRANSITIONS:
        raise Conflict(conflict_message)
    return target


def handoff_offer(
    last_outcome: str | None,
    *,
    rated_not_helpful: bool,
    handoff_active: bool,
) -> HandoffTrigger | None:
    """O motivo da oferta pela última resposta do assistente, ou `None` sem oferta. FR-19.

    Segue a tabela da seção 29.4: `abstained`, `grounding_failed`, `off_topic`, `degraded` e
    `error` oferecem; `answered` só com a nota não útil; `refused` e `cancelled` nunca, nem
    com a nota. Um atendimento ativo na conversa também não oferece outro.
    """
    if handoff_active or last_outcome is None:
        return None
    trigger = _OFFER_BY_OUTCOME.get(last_outcome)
    if trigger is not None:
        return trigger
    if last_outcome == "answered" and rated_not_helpful:
        return HandoffTrigger.NOT_HELPFUL
    return None


def availability(*, enabled: bool, attendants_present: int, queued: int) -> Availability:
    """O status da disponibilidade (seção 29.4), sem dizer quantas pessoas estão presentes.

    A ordem importa: desligado vence tudo, e sem ninguém presente a fila cheia não muda nada.
    """
    if not enabled:
        return Availability.DISABLED
    if attendants_present <= 0:
        return Availability.CLOSED
    if queued >= MAX_QUEUE:
        return Availability.BUSY
    return Availability.OPEN


def is_present(status: str, last_seen_at: datetime, now: datetime) -> bool:
    """Presente: `available` e com sinal do console nos últimos 45 segundos (seção 29.4)."""
    return status == PresenceStatus.AVAILABLE and now - last_seen_at <= PRESENCE_WINDOW


def queue_position(ahead: int) -> int:
    """A posição do visitante: os pedidos na fila feitos antes do dele, mais um (seção 29.5)."""
    return ahead + 1


def is_blocked(last_abusive_closed_at: datetime | None, now: datetime) -> bool:
    """Bloqueio de 24 horas depois de um encerramento `abusive` (seções 29.4 e 29.9.9)."""
    return last_abusive_closed_at is not None and now - last_abusive_closed_at < ABUSE_BLOCK


def has_capacity(assigned_count: int) -> bool:
    """A pessoa pode assumir mais um: tem menos de 3 atendimentos (seção 29.5)."""
    return assigned_count < MAX_PER_ATTENDANT


def close_reason_for_visitor(status: str) -> CloseReason:
    """O motivo quando o visitante encerra: sair da fila ou encerrar o atendimento."""
    if status == HandoffStatus.QUEUED:
        return CloseReason.VISITOR_CANCELLED
    return CloseReason.VISITOR_ENDED


def clean_message(text: str, max_chars: int) -> str | None:
    """O texto do atendimento pronto para gravar, ou `None` quando não serve (seção 29.8).

    Troca `\\r\\n` e `\\r` por `\\n`, exige pelo menos um caractere que não seja espaço e até
    `max_chars` caracteres, e recusa caracteres de controle além de quebra de linha e
    tabulação. Com `None`, o serviço responde 422.
    """
    value = text.replace("\r\n", "\n").replace("\r", "\n")
    if not value.strip() or len(value) > max_chars:
        return None
    if any(_is_control(char) for char in value):
        return None
    return value


def handoff_label_code(handoff_id: UUID, key: str) -> str:
    """Os 8 caracteres do rótulo do atendimento (seção 29.9.4).

    É o HMAC-SHA256 do id do atendimento, não do id da pessoa: dois atendimentos da mesma
    pessoa não se ligam pela tela. Sem `PSEUDONYM_KEY`, como em `test`, vale o começo do
    próprio id, que a equipe já tem na URL.
    """
    if not key:
        return handoff_id.hex[:LABEL_CHARS]
    digest = hmac.new(key.encode("utf-8"), str(handoff_id).encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:LABEL_CHARS]


@dataclass(frozen=True, slots=True)
class StaffMember:
    """A pessoa da equipe de um pedido: o id e o papel, `attendant` ou `admin` (seção 29.3).

    Mora no domínio para os controladores a receberem sem carregar o SQLAlchemy.
    """

    user_id: UUID
    role: str


@dataclass(frozen=True, slots=True)
class HandoffNotice:
    """Um aviso entre processos: o atendimento que mudou, o `seq` e o tipo (ADR-016).

    O fluxo que recebe o aviso nunca confia nele: lê do banco com a própria autorização.
    """

    handoff_id: UUID
    seq: int
    kind: NoticeKind


def parse_notice(payload: str) -> HandoffNotice | None:
    """Lê a carga de um `NOTIFY` de volta. Uma carga fora do formato devolve `None`."""
    try:
        data = json.loads(payload)
        return HandoffNotice(
            handoff_id=UUID(str(data["handoff_id"])),
            seq=int(data["seq"]),
            kind=NoticeKind(str(data["kind"])),
        )
    except (ValueError, KeyError, TypeError):
        return None


def notify_payload(handoff_id: UUID, seq: int, kind: NoticeKind) -> str:
    """A carga do `NOTIFY`: só o id, o `seq` e o tipo, em JSON compacto (ADR-016).

    Fica com menos de 200 bytes e nenhum dado pessoal além do id. Montada à mão, sem
    `json.dumps`, porque os três campos não precisam de escape.
    """
    return f'{{"handoff_id":"{handoff_id}","seq":{int(seq)},"kind":"{kind.value}"}}'


def _is_control(char: str) -> bool:
    """Caractere de controle que não é quebra de linha nem tabulação.

    Cobre o C0, o DEL e o C1 do Unicode, como o byte nulo que o PostgreSQL recusa em texto.
    """
    if char in "\n\t":
        return False
    code = ord(char)
    return code < 0x20 or 0x7F <= code <= 0x9F
