"""Soma de tokens por dia UTC. Seção 8.1 do SDD."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token_usage_day import TokenUsageDay


class TokenUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def totals(self, day: date) -> tuple[int, int]:
        row = await self._session.scalar(select(TokenUsageDay).where(TokenUsageDay.day == day))
        if row is None:
            return (0, 0)
        return (row.input_tokens, row.output_tokens)

    async def add(self, day: date, input_tokens: int, output_tokens: int) -> None:
        statement = (
            insert(TokenUsageDay)
            .values(
                day=day,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            .on_conflict_do_update(
                index_elements=[TokenUsageDay.day],
                set_={
                    "input_tokens": TokenUsageDay.input_tokens + input_tokens,
                    "output_tokens": TokenUsageDay.output_tokens + output_tokens,
                },
            )
        )
        await self._session.execute(statement)
