"""Busca híbrida vista pelo workflow, sem sessão. Seção 8.4 do SDD."""

from collections.abc import Sequence
from typing import Protocol

from app.domain.retrieval import RetrievedChunk


class HybridSearch(Protocol):
    async def search_by_vector(
        self,
        question: str,
        embedding: list[float],
    ) -> Sequence[RetrievedChunk]: ...
