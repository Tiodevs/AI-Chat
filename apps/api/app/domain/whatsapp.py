"""Regras puras do canal WhatsApp: assinatura, leitura do webhook, comandos e formato. Seção 30.

Camada de domínio (seção 6.2): só a biblioteca padrão. Quem usa: o controlador do webhook
(`controllers/whatsapp.py`, pela assinatura), `services/whatsapp_webhook.py` (a leitura do
payload) e `services/whatsapp.py` (o processador, o enviador e o repasse do atendimento).

A Meta documenta o webhook e a Graph API; os nomes dos campos aqui são os dela. A identidade
de quem escreve é o BSUID (ADR-018). O telefone, quando vem, é guardado como dado secundário,
nunca usado como identidade quando há BSUID, e nunca vai para log, rastro, métrica ou console.
"""

import hashlib
import hmac
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any


class Channel(StrEnum):
    """Por onde a conversa chegou: o site ou o WhatsApp (seção 30.7)."""

    WEB = "web"
    WHATSAPP = "whatsapp"


class InboundKind(StrEnum):
    """O tipo de item do webhook gravado em `whatsapp_inbound_events.kind`."""

    MESSAGE = "message"
    STATUS = "status"
    SYSTEM = "system"


class MessageType(StrEnum):
    """O tipo de mensagem recebida que o processador distingue (seção 30.4, passo 6)."""

    TEXT = "text"
    BUTTON = "button"
    MEDIA = "media"
    OTHER = "other"


class InboundStatus(StrEnum):
    """O estado do evento na caixa de entrada (ADR-017)."""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    IGNORED = "ignored"


class OutboundKind(StrEnum):
    """O que a linha da caixa de saída leva."""

    TEXT = "text"
    BUTTONS = "buttons"
    NOTICE = "notice"
    STATUS_UPDATE = "status_update"


class OutboundStatus(StrEnum):
    """O estado da entrega. Os quatro primeiros só andam para frente (seção 30.4, passo 9)."""

    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class Decision(StrEnum):
    """O que o processador fez com a mensagem. Vai no span e no log, nunca o texto."""

    MEDIA = "media"
    BUTTON = "button"
    COMMAND = "command"
    HANDOFF = "handoff"
    RATE_LIMITED = "rate_limited"
    QUESTION = "question"
    IGNORED = "ignored"


class Command(StrEnum):
    """Os comandos de texto, comparados sem maiúsculas e com os espaços juntados."""

    DELETE_DATA = "apagar dados"
    END = "encerrar"


class Button(StrEnum):
    """Os ids dos botões que o Atrium manda. O título visível fica em `prompts/whatsapp.py`."""

    OFFER_YES = "handoff_offer_yes"
    OFFER_NO = "handoff_offer_no"
    CONFIRM_YES = "handoff_confirm_yes"
    CONFIRM_NO = "handoff_confirm_no"
    DELETE_YES = "delete_data_yes"
    DELETE_NO = "delete_data_no"


# O caminho exato do webhook. Só ele fica fora da conferência de `Origin` (seção 30.4).
WEBHOOK_PATH = "/v1/whatsapp/webhook"

# Constantes da seção 30.14.
MAX_WEBHOOK_BYTES = 3 * 1024 * 1024
WAKE_INTERVAL_SECONDS = 2.0
MAX_PROCESS_ATTEMPTS = 3
MAX_SEND_ATTEMPTS = 5
SEND_RETRY_FIRST = timedelta(seconds=30)
SEND_RETRY_MAX = timedelta(minutes=20)
GRAPH_TIMEOUT_SECONDS = 10.0
NEW_CONVERSATION_AFTER = timedelta(hours=24)
CUSTOMER_SERVICE_WINDOW = timedelta(hours=24)
MAX_TEXT_CHARS = 4096
MAX_BUTTONS = 3
MAX_BUTTON_TITLE_CHARS = 20
STALE_EVENT = timedelta(days=7)
STALE_PROCESSING = timedelta(minutes=5)
CONTACT_RETENTION = timedelta(days=30)
EVENT_RETENTION = timedelta(days=7)
MAX_QUESTION_CHARS = 1000
DEFAULT_GRAPH_VERSION = "v23.0"

# Limites da seção 30.8.
QUESTION_WINDOW = timedelta(hours=1)
QUESTION_CONTACT_LIMIT = 20
QUESTION_CONTACT_PURPOSE = "whatsapp_question_contact"
BAD_SIGNATURE_WINDOW = timedelta(minutes=1)
BAD_SIGNATURE_IP_LIMIT = 30
BAD_SIGNATURE_IP_PURPOSE = "whatsapp_bad_signature_ip"

# Erros da Graph API com tratamento próprio (seção 30.4, passo 8).
ERROR_WINDOW_CLOSED = 131047
ERROR_INVALID_TOKEN = 190
ERROR_INVALID_PARAMETER = 100
_RETRYABLE_CODES = frozenset({1, 2, 4, 130429, 131000, 131016, 131056, 133004})

# Prefixos que dizem quem fala (seção 30.5).
AI_PREFIX = "*Atrium (IA):*"
STAFF_PREFIX = "*Equipe do Harborlight:*"

# A identidade sem BSUID: só quando a Meta não manda o BSUID para a empresa (ADR-018).
_PHONE_IDENTITY_PREFIX = "phone:"
_MEDIA_TYPES = frozenset(
    {"image", "audio", "video", "document", "sticker", "location", "contacts", "reaction"}
)
_SENTENCE_END = re.compile(r"[.!?…](?=\s)|\n")
_STATUS_ORDER = {
    OutboundStatus.PENDING: 0,
    OutboundStatus.SENT: 1,
    OutboundStatus.DELIVERED: 2,
    OutboundStatus.READ: 3,
}


@dataclass(frozen=True, slots=True)
class InboundEvent:
    """Um item do webhook, pronto para a caixa de entrada.

    `event_key` é a chave de deduplicação: o `wamid` da mensagem, o `wamid` com o status, ou
    a troca de identidade com o instante. `identity` é o BSUID, ou `phone:<wa_id>` só quando
    a Meta não manda BSUID. `phone` é o `wa_id`, quando vem. `body` só existe em texto.
    """

    event_key: str
    kind: InboundKind
    wa_timestamp: datetime
    identity: str | None = None
    phone: str | None = None
    message_type: MessageType | None = None
    body: str | None = None
    button_id: str | None = None
    wamid: str | None = None
    status: OutboundStatus | None = None
    error_code: int | None = None
    previous_identity: str | None = None


@dataclass(frozen=True, slots=True)
class Recipient:
    """Para quem a Graph API envia: o BSUID em `recipient`, ou o telefone em `to`."""

    bsuid: str | None
    phone: str | None


def verify_signature(body: bytes, header: str | None, app_secret: str) -> bool:
    """Confere `X-Hub-Signature-256` sobre os bytes recebidos (seção 30.8).

    O cabeçalho é `sha256=<hex>` do HMAC-SHA256 do corpo cru com o segredo do app. A
    comparação leva o mesmo tempo para qualquer valor errado. Sem segredo, recusa sempre.
    """
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256=").strip().lower())


def verify_challenge(
    *, mode: str | None, token: str | None, challenge: str | None, verify_token: str
) -> str | None:
    """A verificação do webhook: devolve o desafio quando o modo e o token batem."""
    if not verify_token or mode != "subscribe" or token is None or challenge is None:
        return None
    if not hmac.compare_digest(token.encode("utf-8"), verify_token.encode("utf-8")):
        return None
    return challenge


def parse_webhook(payload: Mapping[str, Any], phone_number_id: str) -> list[InboundEvent]:
    """Os eventos do payload que são do número do Atrium, na ordem em que vieram.

    Ignora `entry` de outro `phone_number_id` e campos que não são `messages`. Um item sem
    os campos mínimos é descartado, em vez de derrubar o webhook: a Meta repetiria para
    sempre um payload que o Atrium não entende.
    """
    events: list[InboundEvent] = []
    if payload.get("object") != "whatsapp_business_account":
        return events
    for entry in _list(payload.get("entry")):
        for change in _list(_dict(entry).get("changes")):
            change_map = _dict(change)
            if change_map.get("field") != "messages":
                continue
            value = _dict(change_map.get("value"))
            metadata = _dict(value.get("metadata"))
            if phone_number_id and str(metadata.get("phone_number_id", "")) != phone_number_id:
                continue
            contacts = [_dict(item) for item in _list(value.get("contacts"))]
            for message in _list(value.get("messages")):
                event = _message_event(_dict(message), contacts)
                if event is not None:
                    events.append(event)
            for status in _list(value.get("statuses")):
                event = _status_event(_dict(status))
                if event is not None:
                    events.append(event)
    return events


def normalize_command(text: str) -> Command | None:
    """O comando do texto, sem maiúsculas, acentos de borda nem espaços repetidos."""
    folded = " ".join(text.split()).casefold().strip(" .!")
    for command in Command:
        if folded == command.value:
            return command
    return None


def is_new_conversation(last_user_message_at: datetime | None, now: datetime) -> bool:
    """Uma conversa nova começa depois de 24 horas sem mensagem da pessoa (seção 30.3)."""
    return last_user_message_at is None or now - last_user_message_at > NEW_CONVERSATION_AFTER


def within_service_window(last_inbound_at: datetime | None, now: datetime) -> bool:
    """O Atrium só envia dentro da janela de 24 horas da Meta (FR-33)."""
    return last_inbound_at is not None and now - last_inbound_at <= CUSTOMER_SERVICE_WINDOW


def is_bsuid(identity: str) -> bool:
    """O BSUID tem duas letras de país e um ponto, como `BR.123` (ADR-018)."""
    return not identity.startswith(_PHONE_IDENTITY_PREFIX) and bool(
        re.fullmatch(r"[A-Z]{2}\.[A-Za-z0-9.]{1,140}", identity)
    )


def recipient_for(identity: str, phone: str | None, *, use_phone: bool = False) -> Recipient:
    """Para quem enviar. O BSUID primeiro; o telefone só sem BSUID ou na segunda tentativa."""
    if is_bsuid(identity) and not use_phone:
        return Recipient(bsuid=identity, phone=None)
    if identity.startswith(_PHONE_IDENTITY_PREFIX):
        return Recipient(bsuid=None, phone=identity.removeprefix(_PHONE_IDENTITY_PREFIX))
    return Recipient(bsuid=None, phone=phone)


def can_fallback_to_phone(identity: str, phone: str | None, error_code: int | None) -> bool:
    """Um parâmetro recusado no envio pelo BSUID tenta de novo pelo telefone guardado."""
    return is_bsuid(identity) and bool(phone) and error_code == ERROR_INVALID_PARAMETER


def is_retryable(*, http_status: int | None, error_code: int | None) -> bool:
    """Se uma falha de envio merece nova tentativa (seção 30.4, passo 8)."""
    if error_code in (ERROR_WINDOW_CLOSED, ERROR_INVALID_TOKEN):
        return False
    if error_code in _RETRYABLE_CODES:
        return True
    return http_status is None or http_status == 429 or http_status >= 500


def next_attempt_delay(attempts: int) -> timedelta:
    """A espera antes da próxima tentativa: 30 s, 1 min, 2 min... até 20 min."""
    delay: timedelta = SEND_RETRY_FIRST * int(2 ** max(0, attempts - 1))
    return min(delay, SEND_RETRY_MAX)


def status_advances(current: str, new: OutboundStatus) -> bool:
    """Um status só substitui outro posterior a ele. `failed` não volta atrás (seção 30.4)."""
    if current == OutboundStatus.FAILED:
        return False
    if new == OutboundStatus.FAILED:
        return current in (OutboundStatus.PENDING, OutboundStatus.SENT)
    return _STATUS_ORDER.get(new, -1) > _STATUS_ORDER.get(OutboundStatus(current), -1)


def to_whatsapp_text(answer: str, sources: Sequence[str], *, prefix: str) -> str:
    """A resposta do pipeline no formato do WhatsApp, em até 4.096 caracteres (seção 30.6).

    1. Converte o Markdown: negrito, itálico, títulos, links e tabelas.
    2. Monta a linha de fontes com os títulos dos documentos citados, sem repetir.
    3. Corta o corpo na última frase que cabe, e as fontes continuam inteiras.
    """
    body = markdown_to_whatsapp(answer).strip()
    unique_sources = list(dict.fromkeys(source.strip() for source in sources if source.strip()))
    footer = ""
    if unique_sources:
        footer = "\n\nFontes:\n" + "\n".join(f"- {source}" for source in unique_sources)
    head = f"{prefix}\n" if prefix else ""
    room = MAX_TEXT_CHARS - len(head) - len(footer)
    return head + _cut(body, max(room, 1)) + footer


def markdown_to_whatsapp(text: str) -> str:
    """Troca a marcação do Markdown pela do WhatsApp, linha a linha."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if re.fullmatch(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?", stripped):
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            line = " — ".join(cell for cell in cells if cell)
        heading = re.match(r"^\s*#{1,6}\s+(.*)$", line)
        if heading:
            line = f"**{heading.group(1).strip()}**"
        lines.append(line)
    joined = "\n".join(lines)
    joined = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"\1 (\2)", joined)
    # O negrito vira um marcador antes, para o itálico de um asterisco não pegá-lo.
    joined = re.sub(r"\*\*(.+?)\*\*", "\x00\\1\x00", joined)
    joined = re.sub(r"__(.+?)__", "\x00\\1\x00", joined)
    joined = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"_\1_", joined)
    return joined.replace("\x00", "*")


def staff_text(content: str) -> str:
    """A mensagem da equipe com o rótulo, cortada no limite da Meta."""
    return _cut(f"{STAFF_PREFIX}\n{content}", MAX_TEXT_CHARS)


def ai_text(content: str) -> str:
    """Um texto fixo do Atrium com o rótulo da IA."""
    return _cut(f"{AI_PREFIX}\n{content}", MAX_TEXT_CHARS)


def button_titles_fit(titles: Iterable[str]) -> bool:
    """Até 3 botões, cada um com até 20 caracteres (limite da Meta)."""
    items = list(titles)
    return 0 < len(items) <= MAX_BUTTONS and all(
        0 < len(title) <= MAX_BUTTON_TITLE_CHARS for title in items
    )


def clean_question(text: str) -> str | None:
    """O texto recebido sem caracteres de controle, de 1 a 1.000 caracteres, ou `None`."""
    kept = "".join(
        char for char in text if char in "\n\t" or unicodedata.category(char)[0] != "C"
    ).strip()
    if not kept:
        return None
    return kept[:MAX_QUESTION_CHARS]


def _cut(text: str, limit: int) -> str:
    """Corta no fim da última frase que cabe; sem nenhuma, corta e põe reticências."""
    if len(text) <= limit:
        return text
    window = text[:limit]
    ends = [match.end() for match in _SENTENCE_END.finditer(window)]
    if ends and ends[-1] > limit // 2:
        return window[: ends[-1]].rstrip()
    return window[: max(limit - 1, 0)].rstrip() + "…"


def _message_event(message: dict[str, Any], contacts: list[dict[str, Any]]) -> InboundEvent | None:
    """Uma mensagem recebida, de texto, botão, mídia, sistema ou outro tipo."""
    wamid = message.get("id")
    timestamp = _timestamp(message.get("timestamp"))
    if not isinstance(wamid, str) or not wamid or timestamp is None:
        return None
    kind_name = message.get("type")
    phone = _str(message.get("from"))
    bsuid = _str(message.get("from_user_id")) or _contact_bsuid(contacts, phone)
    if kind_name == "system":
        system = _dict(message.get("system"))
        new_id = _str(system.get("user_id")) or _str(system.get("wa_id"))
        previous = _str(system.get("previous_user_id")) or bsuid or _phone_identity(phone)
        if not new_id or not previous:
            return None
        return InboundEvent(
            event_key=wamid,
            kind=InboundKind.SYSTEM,
            wa_timestamp=timestamp,
            identity=new_id if is_bsuid(new_id) else _phone_identity(new_id),
            phone=_str(system.get("wa_id")),
            previous_identity=previous,
        )
    identity = bsuid or _phone_identity(phone)
    if identity is None:
        return None
    body: str | None = None
    button_id: str | None = None
    if kind_name == "text":
        message_type = MessageType.TEXT
        body = _str(_dict(message.get("text")).get("body"))
    elif kind_name == "interactive":
        interactive = _dict(message.get("interactive"))
        reply = _dict(interactive.get("button_reply")) or _dict(interactive.get("list_reply"))
        button_id = _str(reply.get("id"))
        message_type = MessageType.BUTTON if button_id else MessageType.OTHER
    elif kind_name == "button":
        button_id = _str(_dict(message.get("button")).get("payload"))
        message_type = MessageType.BUTTON if button_id else MessageType.OTHER
    elif kind_name in _MEDIA_TYPES:
        message_type = MessageType.MEDIA
    else:
        message_type = MessageType.OTHER
    return InboundEvent(
        event_key=wamid,
        kind=InboundKind.MESSAGE,
        wa_timestamp=timestamp,
        identity=identity,
        phone=phone,
        message_type=message_type,
        body=body,
        button_id=button_id,
        wamid=wamid,
    )


def _status_event(status: dict[str, Any]) -> InboundEvent | None:
    """Um status de entrega de uma mensagem que o Atrium enviou."""
    wamid = _str(status.get("id"))
    timestamp = _timestamp(status.get("timestamp"))
    try:
        value = OutboundStatus(str(status.get("status")))
    except ValueError:
        return None
    if not wamid or timestamp is None or value == OutboundStatus.PENDING:
        return None
    error_code: int | None = None
    for error in _list(status.get("errors")):
        code = _dict(error).get("code")
        if isinstance(code, int):
            error_code = code
            break
    return InboundEvent(
        event_key=f"{wamid}:{value.value}",
        kind=InboundKind.STATUS,
        wa_timestamp=timestamp,
        wamid=wamid,
        status=value,
        error_code=error_code,
    )


def _contact_bsuid(contacts: list[dict[str, Any]], phone: str | None) -> str | None:
    """O BSUID do bloco `contacts`, quando a mensagem não traz `from_user_id`."""
    for contact in contacts:
        user_id = _str(contact.get("user_id"))
        if user_id and (phone is None or _str(contact.get("wa_id")) in (None, phone)):
            return user_id
    return None


def _phone_identity(phone: str | None) -> str | None:
    """A identidade de reserva, só quando a Meta não manda BSUID."""
    return f"{_PHONE_IDENTITY_PREFIX}{phone}" if phone else None


def _timestamp(value: object) -> datetime | None:
    """O `timestamp` da Meta, em segundos Unix como texto, em UTC."""
    try:
        return datetime.fromtimestamp(int(str(value)), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
