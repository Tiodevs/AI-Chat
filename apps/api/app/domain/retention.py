"""Prazos de retenção. Cada regra da seção 11.6 vira um corte no tempo.

Meses viram dias corridos: 12 meses são 365 dias e 24 meses são 730.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class RetentionRule(StrEnum):
    INACTIVE_ACCOUNTS = "inactive_accounts"
    MEMBER_CONVERSATIONS = "member_conversations"
    GUEST_CONVERSATIONS = "guest_conversations"
    GUEST_KEYS = "guest_keys"
    REGISTRATION_SESSIONS = "registration_sessions"
    AUTH_SESSIONS = "auth_sessions"
    RATE_LIMIT_WINDOWS = "rate_limit_windows"
    AUDIT_EVENTS = "audit_events"
    PRIVACY_REQUESTS = "privacy_requests"


RETENTION: dict[RetentionRule, timedelta] = {
    RetentionRule.INACTIVE_ACCOUNTS: timedelta(days=730),
    RetentionRule.MEMBER_CONVERSATIONS: timedelta(days=365),
    RetentionRule.GUEST_CONVERSATIONS: timedelta(days=30),
    RetentionRule.GUEST_KEYS: timedelta(days=30),
    # A sessão de cadastro já expira em 24 horas. O corte é o próprio expires_at.
    RetentionRule.REGISTRATION_SESSIONS: timedelta(0),
    RetentionRule.AUTH_SESSIONS: timedelta(days=14),
    RetentionRule.RATE_LIMIT_WINDOWS: timedelta(hours=48),
    RetentionRule.AUDIT_EVENTS: timedelta(days=730),
    RetentionRule.PRIVACY_REQUESTS: timedelta(days=730),
}


@dataclass(frozen=True, slots=True)
class RetentionResult:
    rule: RetentionRule
    deleted_count: int


def cutoff(rule: RetentionRule, now: datetime) -> datetime:
    """Tudo com marca de tempo estritamente anterior ao corte venceu."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now - RETENTION[rule]


def is_expired(rule: RetentionRule, moment: datetime, now: datetime) -> bool:
    return moment < cutoff(rule, now)
