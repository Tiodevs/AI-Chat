"""Contador diário de tokens. Seção 7.1 do SDD.

Camada de portas. `ConversationService`, `QuestionService` e `RegistrationService` consultam o
teto antes de chamar o modelo e registram o uso depois. A implementação é `PostgresTokenBudget`
(`app/services/budget.py`), que grava em `token_usage_days` e usa as regras de
`app/domain/budget.py`. Os testes de unidade usam um orçamento em memória.
"""

from typing import Protocol


class TokenBudget(Protocol):
    """Teto de tokens do dia UTC, o mesmo para perguntas e cadastro (seção 7.1)."""

    async def exceeded(self) -> bool:
        """Diz se o uso do dia já alcançou o teto. Com o teto em zero, devolve sempre falso.

        No `PostgresTokenBudget`, abre uma transação curta, atualiza a métrica
        `atrium_llm_budget_ratio` e registra `budget.warning` ou `budget.exceeded` no log.
        """
        ...

    async def record(self, input_tokens: int, output_tokens: int) -> None:
        """Soma os tokens de entrada e de saída ao dia.

        Quem chama registra também o uso de uma resposta cancelada ou quebrada no meio, porque
        o Google cobra esses tokens (seção 7.1). No `PostgresTokenBudget`, valores negativos ou
        os dois zero não gravam nada.
        """
        ...
