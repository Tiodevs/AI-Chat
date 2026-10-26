import logging
import re
import sys
from collections.abc import MutableMapping
from typing import cast

import structlog
from structlog.typing import EventDict, WrappedLogger

from app import __version__

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
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\(\d{3}\)\s*\d{3}-\d{4}|\+\d[\d\s().-]{7,}\d|\d{3}-\d{3}-\d{4})(?!\w)"
)
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
    without_email = _EMAIL_RE.sub("[redacted-email]", value)
    return _PHONE_RE.sub("[redacted-phone]", without_email)


def _scrub(value: object) -> object:
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
    """Remove a lista de recusa e mascara e-mail e telefone. Seção 18.1 do SDD."""
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
    event_dict.setdefault("app_version", __version__)
    for field in _REQUIRED_FIELDS:
        event_dict.setdefault(field, None)
    return event_dict


def configure_logging(log_level: str) -> None:
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
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )


def log_http_request(
    *,
    request_id: str,
    route: str,
    status_code: int,
    duration_ms: int,
) -> None:
    structlog.get_logger("atrium").info(
        "http.request",
        request_id=request_id,
        trace_id=None,
        span_id=None,
        route=route,
        status_code=status_code,
        duration_ms=duration_ms,
        app_version=__version__,
    )
