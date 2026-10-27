"""Porta de embedding. Seção 17 do SDD."""

from typing import Protocol


class EmbeddingProvider(Protocol):
    model_name: str
    dimensions: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...
