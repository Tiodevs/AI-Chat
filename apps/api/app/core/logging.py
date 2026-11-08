"""Log JSON na stdout, com a redação de dados pessoais. Seção 18.1 do SDD (NFR-7).

Camada de núcleo. `configure_logging` liga o `structlog` em `create_app` e nos scripts.
`log_http_request` escreve a linha `http.request` de cada pedido e é chamado pelo
`RequestIdMiddleware`. Os outros módulos só pedem `structlog.get_logger("atrium")`.

Cada evento passa pela cadeia de processadores, nesta ordem:

1. as variáveis de contexto, como o `request_id` que o middleware vinculou;
2. o nível e o `timestamp` ISO em UTC;
3. `redact_sensitive`, que tira as chaves da lista de recusa e mascara e-mail e telefone;
4. `ensure_log_fields`, que garante os campos obrigatórios, com `null` quando faltam;
5. o JSON, impresso na stdout.

Só os eventos do `structlog` passam por essa cadeia. O log de acesso do Uvicorn e os logs da
biblioteca padrão, como os do Alembic, saem pelo `logging` e não são redigidos aqui.
"""

import logging
import re
from collections.abc import MutableMapping
from typing import cast

import structlog
from structlog.typing import EventDict, WrappedLogger

from app import __version__
from app.core.telemetry import span_ids

# Lista de recusa da seção 18.1. A comparação ignora a caixa e vale em qualquer nível de um
# dicionário aninhado. O nome tem de ser exato: `ip` sai, `client_ip` não.
_DENIED_KEYS = frozenset(
    {
        "password",
        "email",
        "phone",
        "text",
        "content",
        "body",
        "authorization",
        "cookie",
        "ip",
    }
)
# Regex aplicadas aos valores que sobram (seção 18.1). O telefone casa `(555) 014-2600`,
# `555-014-2600` e números com `+` de pelo menos 10 caracteres. As bordas `(?<!\w)` e `(?!\w)`
# impedem casar dígitos no meio de uma palavra, como num id.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\(\d{3}\)\s*\d{3}-\d{4}|\+\d[\d\s().-]{7,}\d|\d{3}-\d{3}-\d{4})(?!\w)"
)
# Campos obrigatórios de toda linha (seção 18.1). Os ausentes saem `null`, para o JSON ter
# sempre as mesmas chaves.
_REQUIRED_FIELDS = (
    "timestamp",
    "level",
    "event",
    "request_id",
    "trace_id",
    "span_id",
    "route",
    "status_code",
    "duration_ms",
    "app_version",
)


def _redact_text(value: str) -> str:
    """Troca e-mails por `[redacted-email]` e telefones por `[redacted-phone]`."""
    without_email = _EMAIL_RE.sub("[redacted-email]", value)
    return _PHONE_RE.sub("[redacted-phone]", without_email)


def _scrub(value: object) -> object:
    """Aplica a redação em profundidade: textos, dicionários e listas.

    Num dicionário, as chaves da lista de recusa saem com o valor. Tupla, número e outros
    tipos passam sem mudança.
    """
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        scrubbed: dict[str, object] = {}
        for key, item in value.items():
            if str(key).lower() in _DENIED_KEYS:
                continue
            scrubbed[str(key)] = _scrub(item)
        return scrubbed
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def redact_sensitive(
    _logger: WrappedLogger,
    _method: str,
    event_dict: EventDict,
) -> EventDict:
    """Remove a lista de recusa e mascara e-mail e telefone. Seção 18.1 do SDD.

    Processador do `structlog`: recebe o evento como dicionário, inclusive o texto de `event`,
    e o reescreve no mesmo objeto com a versão limpa.
    """
    scrubbed = _scrub(dict(event_dict))
    if isinstance(scrubbed, dict):
        event_dict.clear()
        event_dict.update(cast(MutableMapping[str, object], scrubbed))
    return event_dict


def ensure_log_fields(
    _logger: WrappedLogger,
    _method: str,
    event_dict: EventDict,
) -> EventDict:
    """Processador que garante `app_version` e os demais campos obrigatórios, `None` se faltam."""
    event_dict.setdefault("app_version", __version__)
    for field in _REQUIRED_FIELDS:
        event_dict.setdefault(field, None)
    return event_dict


def configure_logging(log_level: str) -> None:
    """Liga o `structlog` com a cadeia da seção 18.1 e o nível de `LOG_LEVEL`.

    Um nome de nível desconhecido vale `INFO`. O logger filtrante descarta o que fica abaixo
    do nível antes de montar o evento. Sem cache de logger, uma nova chamada, como a de cada
    `create_app` nos testes, vale para os `get_logger` seguintes.
    """
    level = logging.getLevelNamesMapping().get(log_level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
            redact_sensitive,
            ensure_log_fields,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def log_http_request(
    *,
    request_id: str,
    route: str,
    status_code: int,
    duration_ms: int,
) -> None:
    """Escreve a linha `http.request` de um pedido, com o `trace_id` e o `span_id` correntes.

    Sem span ativo, como fora do `opentelemetry-instrument`, os dois saem `null`.
    """
    trace_id, span_id = span_ids()
    structlog.get_logger("atrium").info(
        "http.request",
        request_id=request_id,
        trace_id=trace_id,
        span_id=span_id,
        route=route,
        status_code=status_code,
        duration_ms=duration_ms,
        app_version=__version__,
    )
