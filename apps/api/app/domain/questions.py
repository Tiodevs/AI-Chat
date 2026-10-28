"""Regras da pergunta por HTTP: dono, marcador, cookie e baldes. Seções 7.1, 8.1 e 10.4."""

from datetime import datetime, timedelta
from uuid import UUID

from app.domain.auth import (
    RateDecision,
    SessionCookie,
    retry_after_seconds,
    session_cookie_is_secure,
)

HEALTH_MESSAGE_MARKER = "[health-related message not stored]"
MAX_QUESTION_CHARS = 1000
GUEST_COOKIE_NAME = "atrium_guest"
GUEST_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
QUESTION_WINDOW = timedelta(hours=1)
GUEST_QUESTION_KEY_LIMIT = 30
GUEST_QUESTION_IP_LIMIT = 60
MEMBER_QUESTION_LIMIT = 120
DIAGNOSTICS_WINDOW = timedelta(hours=1)
DIAGNOSTICS_IP_LIMIT = 60
QUESTION_GUEST_KEY_PURPOSE = "question_guest"
QUESTION_GUEST_IP_PURPOSE = "question_ip"
QUESTION_MEMBER_PURPOSE = "question_member"
DIAGNOSTICS_IP_PURPOSE = "diagnostics_ip"


def stored_user_content(*, intent: str | None, text: str) -> str:
    """Orientação médica não fica gravada. O restante entra como foi enviado."""
    if intent == "medical_advice":
        return HEALTH_MESSAGE_MARKER
    return text


def owns_conversation(
    *,
    actor_user_id: UUID | None,
    actor_guest_key_id: UUID | None,
    owner_user_id: UUID | None,
    owner_guest_key_id: UUID | None,
) -> bool:
    if actor_user_id is not None and actor_user_id == owner_user_id:
        return True
    return actor_guest_key_id is not None and actor_guest_key_id == owner_guest_key_id


def guest_cookie(*, secret: str, app_env: str) -> SessionCookie:
    return SessionCookie(
        name=GUEST_COOKIE_NAME,
        value=secret,
        http_only=True,
        same_site="lax",
        secure=session_cookie_is_secure(app_env),
        path="/",
        max_age=GUEST_MAX_AGE_SECONDS,
    )


def guest_question_rate_decision(
    *,
    key_count: int,
    ip_count: int,
    now: datetime,
    window_start: datetime,
) -> RateDecision:
    retries: list[int] = []
    if key_count > GUEST_QUESTION_KEY_LIMIT:
        retries.append(retry_after_seconds(now, window_start, QUESTION_WINDOW))
    if ip_count > GUEST_QUESTION_IP_LIMIT:
        retries.append(retry_after_seconds(now, window_start, QUESTION_WINDOW))
    if not retries:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(limited=True, retry_after_seconds=max(retries))


def member_question_rate_decision(
    *,
    user_count: int,
    now: datetime,
    window_start: datetime,
) -> RateDecision:
    if user_count <= MEMBER_QUESTION_LIMIT:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(
        limited=True,
        retry_after_seconds=retry_after_seconds(now, window_start, QUESTION_WINDOW),
    )


def diagnostics_rate_decision(
    *,
    ip_count: int,
    now: datetime,
    window_start: datetime,
) -> RateDecision:
    if ip_count <= DIAGNOSTICS_IP_LIMIT:
        return RateDecision(limited=False, retry_after_seconds=0)
    return RateDecision(
        limited=True,
        retry_after_seconds=retry_after_seconds(now, window_start, DIAGNOSTICS_WINDOW),
    )
