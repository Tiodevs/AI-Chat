"""Roda as regras de retenção da seção 11.6, cada uma na própria transação."""

from collections.abc import Awaitable, Callable
from datetime import datetime

import structlog

from app.core.metrics import RETENTION_DELETED
from app.core.telemetry import traced_span
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.retention import RetentionResult, RetentionRule, cutoff
from app.ports.clock import Clock
from app.repositories.retention import RetentionRepository

_Step = Callable[[RetentionRepository, datetime], Awaitable[int]]

# A ordem importa: contas inativas saem antes das conversas e das sessões delas.
RULES: tuple[tuple[RetentionRule, _Step], ...] = (
    (RetentionRule.INACTIVE_ACCOUNTS, RetentionRepository.delete_inactive_accounts),
    (RetentionRule.MEMBER_CONVERSATIONS, RetentionRepository.delete_member_conversations),
    (RetentionRule.GUEST_CONVERSATIONS, RetentionRepository.delete_guest_conversations),
    (RetentionRule.GUEST_KEYS, RetentionRepository.delete_guest_keys),
    (RetentionRule.REGISTRATION_SESSIONS, RetentionRepository.delete_registration_sessions),
    (RetentionRule.AUTH_SESSIONS, RetentionRepository.delete_auth_sessions),
    (RetentionRule.RATE_LIMIT_WINDOWS, RetentionRepository.delete_rate_limit_windows),
    (RetentionRule.AUDIT_EVENTS, RetentionRepository.delete_audit_events),
    (RetentionRule.PRIVACY_REQUESTS, RetentionRepository.delete_privacy_requests),
)


class RetentionService:
    def __init__(self, *, database_url: str, clock: Clock) -> None:
        self._database_url = database_url
        self._clock = clock

    async def run_rule(self, rule: RetentionRule) -> RetentionResult:
        step = dict(RULES)[rule]
        now = self._clock.now()
        with traced_span("retention.run", rule=rule.value) as span:
            async with open_session(self._database_url) as session, UnitOfWork(session):
                deleted = await step(RetentionRepository(session), cutoff(rule, now))
            span.set(deleted_count=deleted)
        RETENTION_DELETED.labels(rule=rule.value).inc(deleted)
        structlog.get_logger("atrium").info("retention.run", rule=rule.value, deleted_count=deleted)
        return RetentionResult(rule=rule, deleted_count=deleted)

    async def run_all(self) -> list[RetentionResult]:
        return [await self.run_rule(rule) for rule, _ in RULES]
