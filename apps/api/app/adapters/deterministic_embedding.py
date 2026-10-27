"""Vetor unitário estável, gerado por hash. Seção 17 do SDD."""

import hashlib
import math

from app.models.vector import EMBEDDING_DIMENSIONS


class DeterministicEmbeddingProvider:
    def __init__(
        self,
        dimensions: int = EMBEDDING_DIMENSIONS,
        model_name: str = "deterministic",
    ) -> None:
        self.dimensions = dimensions
        self.model_name = model_name

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [_unit_vector(text, self.dimensions) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return _unit_vector(text, self.dimensions)


def _unit_vector(text: str, dimensions: int) -> list[float]:
    values: list[float] = []
    seed = text.encode()
    counter = 0
    while len(values) < dimensions:
        block = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        counter += 1
        for offset in range(0, len(block), 4):
            piece = block[offset : offset + 4]
            if len(piece) < 4:
                break
            raw = int.from_bytes(piece, "big")
            values.append(raw / 4294967295 * 2 - 1)
    selected = values[:dimensions]
    norm = math.sqrt(sum(value * value for value in selected))
    if norm == 0:
        selected[0] = 1.0
        return selected
    return [value / norm for value in selected]
