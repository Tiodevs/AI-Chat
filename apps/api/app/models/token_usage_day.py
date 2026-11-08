"""Tabela `token_usage_days`: o contador diário de tokens do orçamento. Seções 7.1 e 8.1.

Camada de entidade de persistência (seção 6.2 do SDD). `TokenUsageRepository` soma e lê o
contador para o `PostgresTokenBudget`, e `InsightsRepository.tokens_on` mostra o uso do dia ao
admin. Criada na migração `0003_token_usage`.
"""

from datetime import date

from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TokenUsageDay(Base):
    """Tokens de entrada e de saída gastos num dia UTC.

    A soma das duas colunas é comparada com `LLM_DAILY_TOKEN_BUDGET` (seção 7.1). Ficar no
    PostgreSQL, e não na memória, faz o teto valer para todas as réplicas (seção 6.5). A tabela
    não tem dado pessoal nem regra de retenção.
    """

    __tablename__ = "token_usage_days"

    # O dia UTC é a chave primária, então cada dia tem uma linha só, e o upsert soma nela.
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
