"""Roda as regras de retenção da seção 11.6, cada uma na própria transação.

Camada de serviço. O `retention-job`, tarefa agendada da Railway que roda todo dia às
06:00 UTC (seções 11.6 e 22.1), executa `scripts/retention.py`, que chama
`RetentionService.run_all`. O job roda em outro processo, sem o `lifespan` da API, então
cada transação usa uma conexão própria (seção 6.4).

Cada regra é um método de `RetentionRepository`, com o corte calculado em
`domain/retention.py`. A mesma transação apaga e grava a linha de `retention_runs`, que o
`GET /metrics` da API lê para `atrium_retention_*` (seção 18.3, via `ops_metrics.py`). Cada
regra também abre o span `retention.run` (seção 18.2) e registra o log `retention.run`.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime

import structlog

from app.core.telemetry import traced_span
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.retention import RetentionResult, RetentionRule, cutoff
from app.ports.clock import Clock
from app.repositories.retention import RetentionRepository

# Um apagamento: recebe o repositório e o corte, e devolve quantas linhas saíram.
_Step = Callable[[RetentionRepository, datetime], Awaitable[int]]

# A ordem importa: contas inativas saem antes das conversas e das sessões delas.
# As conversas de convidado vencidas saem antes das chaves de convidado: apagar uma chave
# apaga em cascata as conversas de convidado que ainda forem dela.
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
    (RetentionRule.HANDOFF_CONTENT, RetentionRepository.purge_handoff_content),
    (RetentionRule.WHATSAPP_CONTACTS, RetentionRepository.delete_whatsapp_contacts),
    (RetentionRule.WHATSAPP_EVENTS, RetentionRepository.delete_whatsapp_events),
)


class RetentionService:
    """Aplica as regras de `RULES`. Não tem estado além da URL do banco e do relógio."""

    def __init__(self, *, database_url: str, clock: Clock) -> None:
        self._database_url = database_url
        self._clock = clock

    async def run_rule(self, rule: RetentionRule) -> RetentionResult:
        """Aplica uma regra e devolve quantas linhas ela apagou.

        1. Calcula o corte da regra a partir de agora (`domain/retention.py:cutoff`).
        2. Numa transação, apaga o que venceu e grava a execução em `retention_runs`.
           Como as duas gravações confirmam juntas, a métrica nunca conta um apagamento
           desfeito.
        3. Põe a contagem no span e no log `retention.run`, sem dado pessoal.
        """
        step = dict(RULES)[rule]
        # 1. O mesmo instante vale para o corte e para `ran_at`.
        now = self._clock.now()
        with traced_span("retention.run", rule=rule.value) as span:
            # 2. Apagamento e registro da execução na mesma transação.
            async with open_session(self._database_url) as session, UnitOfWork(session):
                repository = RetentionRepository(session)
                deleted = await step(repository, cutoff(rule, now))
                await repository.record_run(rule.value, deleted, now)
            # 3. Só ids e contagens saem do processo.
            span.set(deleted_count=deleted)
        structlog.get_logger("atrium").info("retention.run", rule=rule.value, deleted_count=deleted)
        return RetentionResult(rule=rule, deleted_count=deleted)

    async def run_all(self) -> list[RetentionResult]:
        """Roda todas as regras em sequência, na ordem de `RULES`.

        Cada regra confirma a própria transação. Uma regra que falha interrompe as
        seguintes, mas não desfaz as que já rodaram.
        """
        return [await self.run_rule(rule) for rule, _ in RULES]
