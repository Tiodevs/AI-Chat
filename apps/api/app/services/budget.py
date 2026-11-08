"""Orçamento diário de tokens no PostgreSQL. Seção 7.1 do SDD, "Orçamento e degradação".

Camada de serviço. `PostgresTokenBudget` implementa a porta `TokenBudget`
(`app/ports/budget.py`) sobre a tabela `token_usage_days`, por meio de
`TokenUsageRepository`. `core/container.py` cria um por pedido para `ConversationService` e
`RegistrationService`, e o script `scripts/ask.py` o passa ao `QuestionService`.

As regras ficam em `domain/budget.py`: o dia é UTC, zero desliga o teto, acima de 80% avisa
e a partir de 100% degrada. A conferência e a soma são passos separados, cada um com a
própria transação curta e sem reserva de tokens: pedidos simultâneos podem passar todos pela
conferência e somar um pouco além do teto.
"""

import structlog

from app.core.metrics import LLM_BUDGET_RATIO
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.budget import BudgetLevel, budget_level, usage_day
from app.ports.clock import Clock
from app.repositories.token_usage import TokenUsageRepository


class PostgresTokenBudget:
    """Teto diário de tokens de entrada e saída, somados.

    `daily_budget` vem de `LLM_DAILY_TOKEN_BUDGET`. Zero ou menos desliga o teto, o que só é
    aceito com `APP_ENV` `local` ou `test`: em `development` e `production` a API não sobe
    assim (`core/config.py:require_safeguards`).
    """

    def __init__(self, database_url: str, clock: Clock, daily_budget: int) -> None:
        self._database_url = database_url
        self._clock = clock
        self._daily_budget = daily_budget

    async def exceeded(self) -> bool:
        """Diz se o uso do dia já alcançou o teto, inclusive quando o iguala.

        Lê o total do dia UTC numa transação curta de leitura. Atualiza o gauge
        `atrium_llm_budget_ratio`, que só muda quando alguém confere o orçamento, e registra
        `budget.warning` acima de 80% ou `budget.exceeded` a partir de 100%. Com o teto
        desligado, devolve `False` sem abrir o banco e sem mexer no gauge.
        """
        if self._daily_budget <= 0:
            return False
        incoming, outgoing = await self._totals()
        level = budget_level(incoming, outgoing, self._daily_budget)
        ratio = (incoming + outgoing) / self._daily_budget
        LLM_BUDGET_RATIO.set(ratio)
        log_budget(level, ratio)
        return level is BudgetLevel.EXCEEDED

    async def record(self, input_tokens: int, output_tokens: int) -> None:
        """Soma o uso de um pedido à linha do dia UTC do momento da gravação.

        Grava mesmo com o teto desligado, porque o contador continua valendo (seção 7.1).
        A soma é um upsert atômico (`INSERT ... ON CONFLICT DO UPDATE` em
        `TokenUsageRepository.add`), então pedidos simultâneos não perdem tokens. Valores
        negativos e o par zero e zero não abrem transação.
        """
        if input_tokens < 0 or output_tokens < 0:
            return
        if input_tokens == 0 and output_tokens == 0:
            return
        async with open_session(self._database_url) as session, UnitOfWork(session):
            await TokenUsageRepository(session).add(
                usage_day(self._clock.now()),
                input_tokens,
                output_tokens,
            )

    async def _totals(self) -> tuple[int, int]:
        """Tokens de entrada e de saída do dia UTC atual. Sem linha, `(0, 0)`."""
        async with open_session(self._database_url) as session, UnitOfWork(session):
            totals = await TokenUsageRepository(session).totals(usage_day(self._clock.now()))
        return totals


def log_budget(level: BudgetLevel, ratio: float) -> None:
    """Registra o nível do orçamento a cada conferência, não uma vez por dia.

    Abaixo de 80% não registra nada. O log leva só a razão, com quatro casas. O alerta do
    Prometheus para o mesmo limiar usa o gauge (seção 18.3).
    """
    if level is BudgetLevel.OPEN:
        return
    event = "budget.exceeded" if level is BudgetLevel.EXCEEDED else "budget.warning"
    structlog.get_logger("atrium").warning(event, ratio=round(ratio, 4))
