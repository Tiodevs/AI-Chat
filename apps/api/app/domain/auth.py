"""Regras puras de sessão, origem e limite de login. Seções 8.1, 10.3 e 10.4."""

import hashlib
import hmac
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Literal

SESSION_COOKIE_NAME = "atrium_session"
SESSION_MAX_AGE_SECONDS = 14 * 24 * 60 * 60
LOGIN_EMAIL_LIMIT = 10
LOGIN_EMAIL_WINDOW = timedelta(minutes=15)
LOGIN_IP_LIMIT = 30
LOGIN_IP_WINDOW = timedelta(hours=1)
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 72
_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True, slots=True)
class SessionCookie:
    name: str
    value: str
    http_only: bool
    same_site: Literal["lax"]
    secure: bool
    path: str
    max_age: int


@dataclass(frozen=True, slots=True)
class RateDecision:
    limited: bool
    retry_after_seconds: int


def normalize_email(email: str) -> str:
    return email.strip().lower()


def email_is_valid(email: str) -> bool:
    if " " in email or email.count("@") != 1:
        return False
    local, domain = email.split("@")
    return bool(local) and "." in domain and not domain.startswith(".") and not domain.endswith(".")


def password_length_is_valid(password: str) -> bool:
    return MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH


def password_is_checkable(password: str) -> bool:
    """Senhas fora de 1 a 72 caracteres não vão ao argon2."""
    return 1 <= len(password) <= MAX_PASSWORD_LENGTH


def hash_session_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def clean_user_agent(value: str) -> str:
    return value.replace("\x00", "")[:512]


def session_cookie_is_secure(app_env: str) -> bool:
    return app_env != "local"


def session_cookie(*, secret: str, app_env: str) -> SessionCookie:
    return SessionCookie(
        name=SESSION_COOKIE_NAME,
        value=secret,
        http_only=True,
        same_site="lax",
        secure=session_cookie_is_secure(app_env),
        path="/",
        max_age=SESSION_MAX_AGE_SECONDS,
    )


def origin_is_allowed(*, method: str, origin: str | None, web_origin: str) -> bool:
    if method.upper() not in _STATE_CHANGING_METHODS:
        return True
    return bool(origin) and origin == web_origin


def fixed_window_start(now: datetime, window: timedelta) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    size = int(window.total_seconds())
    if size <= 0:
        raise ValueError("window must be positive")
    moment = now.astimezone(UTC)
    epoch = int(moment.timestamp())
    return datetime.fromtimestamp(epoch - (epoch % size), tz=UTC)


def retry_after_seconds(now: datetime, window_start: datetime, window: timedelta) -> int:
    remaining = (window_start + window - now.astimezone(UTC)).total_seconds()
    return max(1, math.ceil(remaining))


def bucket_key(*, purpose: str, subject: str, day: date, key: str) -> str:
    """HMAC com sal do dia. O IP cru e o e-mail não entram na chave gravada."""
    if not key:
        raise ValueError("hmac key is empty")
    digest = hmac.new(
        key.encode("utf-8"),
        f"{purpose}|{day.isoformat()}|{subject}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{purpose}:{digest}"


def login_rate_decision(
    *,
    email_count: int,
    ip_count: int,
    now: datetime,
    email_window_start: datetime,
    ip_window_start: datetime,
) -> RateDecision:
    retries: list[int] = []
    if email_count > LOGIN_EMAIL_LIMIT:
        retries.append(retry_after_seconds(now, email_window_start, LOGIN_EMAIL_WINDOW))
    if ip_count > LOGIN_IP_LIMIT:
        retries.append(retry_after_seconds(now, ip_window_start, LOGIN_IP_WINDOW))
    if not retries:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(limited=True, retry_after_seconds=max(retries))
