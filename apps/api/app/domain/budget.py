"""Teto diário de tokens. Seção 7.1 do SDD.

Camada de domínio. `PostgresTokenBudget` (`app/services/budget.py`), que implementa a porta
`TokenBudget`, soma o uso do dia em `token_usage_days` e pergunta o nível a `budget_level`.
O nível decide se a pergunta degrada e se o cadastro por chat oferece só o formulário
(seção 7.1, "Orçamento e degradação").
"""

from datetime import UTC, date, datetime
from enum import StrEnum

# Acima de 80% do teto, a API registra o log `budget.warning` (seção 7.1). O alerta de
# orçamento do Grafana usa o mesmo limiar (seção 18.3).
WARNING_RATIO = 0.8


class BudgetLevel(StrEnum):
    """Nível do uso do dia em relação ao teto.

    `EXCEEDED` faz a pergunta receber a resposta fixa de indisponibilidade, com desfecho
    `degraded`, e o cadastro por chat responder 503. `WARNING` só gera o log.
    """

    OPEN = "open"
    WARNING = "warning"
    EXCEEDED = "exceeded"


def usage_day(moment: datetime) -> date:
    """O dia do contador é UTC. Seção 7.1 do SDD.

    Um `datetime` sem fuso é tratado como se já estivesse em UTC.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).date()


def budget_level(input_tokens: int, output_tokens: int, daily_budget: int) -> BudgetLevel:
    """Zero desliga o teto. A partir de 100% degrada. Acima de 80% avisa.

    A soma de entrada e saída é comparada com `daily_budget`. O uso igual ao teto já estoura
    (`>= 1`), e o aviso exige passar de 80% (`> 0.8`). O teto zero ou negativo só vale em
    `local` e `test`: a subida da API o recusa em `development` e `production` (seção 7.1).
    """
    if daily_budget <= 0:
        return BudgetLevel.OPEN
    ratio = (input_tokens + output_tokens) / daily_budget
    if ratio >= 1:
        return BudgetLevel.EXCEEDED
    if ratio > WARNING_RATIO:
        return BudgetLevel.WARNING
    return BudgetLevel.OPEN
