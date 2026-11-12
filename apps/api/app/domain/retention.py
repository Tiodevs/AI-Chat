"""Prazos de retenção. Cada regra da seção 11.6 vira um corte no tempo.

Meses viram dias corridos: 12 meses são 365 dias e 24 meses são 730.

Camada de domínio. `RetentionService` (`app/services/retention.py`) roda cada regra numa
transação própria, com o corte de `cutoff`, e `RetentionRepository` apaga as linhas mais
antigas que ele. O `retention-job` da Railway chama `python -m app.scripts.retention` todo dia
às 06:00 UTC.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class RetentionRule(StrEnum):
    """Uma regra da tabela da seção 11.6.

    O valor vai para `retention_runs.rule` e para o rótulo `rule` da métrica
    `atrium_retention_deleted` (seção 18.3).
    """

    INACTIVE_ACCOUNTS = "inactive_accounts"
    MEMBER_CONVERSATIONS = "member_conversations"
    GUEST_CONVERSATIONS = "guest_conversations"
    GUEST_KEYS = "guest_keys"
    REGISTRATION_SESSIONS = "registration_sessions"
    AUTH_SESSIONS = "auth_sessions"
    RATE_LIMIT_WINDOWS = "rate_limit_windows"
    AUDIT_EVENTS = "audit_events"
    PRIVACY_REQUESTS = "privacy_requests"
    HANDOFF_CONTENT = "handoff_content"


# Prazo de cada regra. O repositório compara com um marco diferente por regra: `last_seen_at`
# nas contas de membro, a mensagem mais nova (ou a criação) nas conversas, `created_at` nas
# chaves de convidado e na auditoria, `expires_at` no cadastro, `expires_at` ou `revoked_at`
# nas sessões, `window_start` nos limites de taxa e `closed_at` nos pedidos fechados.
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
    # O texto do atendimento humano, 90 dias depois de `closed_at` (seção 29.9.9).
    RetentionRule.HANDOFF_CONTENT: timedelta(days=90),
}


@dataclass(frozen=True, slots=True)
class RetentionResult:
    """Quantas linhas uma regra apagou numa execução. Vai para `retention_runs`."""

    rule: RetentionRule
    deleted_count: int


def cutoff(rule: RetentionRule, now: datetime) -> datetime:
    """Tudo com marca de tempo estritamente anterior ao corte venceu.

    Levanta `ValueError` com `now` sem fuso.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now - RETENTION[rule]


def is_expired(rule: RetentionRule, moment: datetime, now: datetime) -> bool:
    """Diz se um marco de tempo já passou do corte da regra.

    Só os testes usam esta função; o repositório faz a mesma comparação no SQL.
    """
    return moment < cutoff(rule, now)
