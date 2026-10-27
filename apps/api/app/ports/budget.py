"""Contador diário de tokens. Seção 7.1 do SDD."""

from typing import Protocol


class TokenBudget(Protocol):
    async def exceeded(self) -> bool: ...

    async def record(self, input_tokens: int, output_tokens: int) -> None: ...
