"""Soma de tokens por dia UTC. Seção 8.1 do SDD.

Camada de repositório (seção 6.2 do SDD). Lê e grava `token_usage_days`. Quem usa é o
`PostgresTokenBudget`: `totals` antes de cada pergunta e de cada turno do cadastro por chat,
para saber se o orçamento estourou, e `add` depois deles, com o uso que os adaptadores
contaram. Seção 7.1 do SDD.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token_usage_day import TokenUsageDay


class TokenUsageRepository:
    """Contador diário de tokens, uma linha por dia UTC."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def totals(self, day: date) -> tuple[int, int]:
        """(entrada, saída) gastos no dia, ou `(0, 0)` sem linha. Busca pela chave primária."""
        row = await self._session.scalar(select(TokenUsageDay).where(TokenUsageDay.day == day))
        if row is None:
            return (0, 0)
        return (row.input_tokens, row.output_tokens)

    async def add(self, day: date, input_tokens: int, output_tokens: int) -> None:
        """Soma os tokens ao dia, criando a linha no primeiro uso.

        Upsert do PostgreSQL: `INSERT ... ON CONFLICT (day) DO UPDATE` soma ao valor gravado.
        A soma acontece no banco, com a linha travada pelo UPDATE, então dois pedidos
        simultâneos não perdem tokens um do outro.
        """
        statement = (
            insert(TokenUsageDay)
            .values(
                day=day,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            .on_conflict_do_update(
                index_elements=[TokenUsageDay.day],
                # Dentro do `DO UPDATE`, as colunas da entidade são os valores já gravados.
                set_={
                    "input_tokens": TokenUsageDay.input_tokens + input_tokens,
                    "output_tokens": TokenUsageDay.output_tokens + output_tokens,
                },
            )
        )
        await self._session.execute(statement)
