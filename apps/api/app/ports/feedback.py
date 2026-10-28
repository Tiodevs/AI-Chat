"""Porta do feedback. Seção 17 do SDD."""

from typing import Protocol
from uuid import UUID


class FeedbackSink(Protocol):
    async def record(self, run_id: UUID, key: str, score: float) -> None: ...
