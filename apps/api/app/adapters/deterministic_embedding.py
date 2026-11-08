"""Vetor unitário estável, gerado por hash. Seção 17 do SDD.

Implementa a porta `EmbeddingProvider` para os testes (ADR-004): o mesmo texto devolve sempre
o mesmo vetor, sem rede. Textos diferentes dão vetores sem relação de sentido, então só o
texto idêntico fica perto. Por isso a e2e usa o `LexicalEmbeddingProvider` (ADR-014).

Quem usa: `build_embedding_provider` com `APP_AI_ADAPTER=fake` e os testes de integração de
busca, semente e documentos, que o injetam direto.
"""

import hashlib
import math

from app.models.vector import EMBEDDING_DIMENSIONS


class DeterministicEmbeddingProvider:
    """Vetores por hash do texto inteiro, com norma 1 e 768 dimensões por padrão."""

    def __init__(
        self,
        dimensions: int = EMBEDDING_DIMENSIONS,
        model_name: str = "deterministic",
    ) -> None:
        self.dimensions = dimensions
        self.model_name = model_name

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Um vetor por texto, na ordem recebida."""
        return [_unit_vector(text, self.dimensions) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        """O vetor da pergunta, pela mesma regra dos documentos."""
        return _unit_vector(text, self.dimensions)


def _unit_vector(text: str, dimensions: int) -> list[float]:
    """Um vetor estável para o texto.

    1. Encadeia SHA-256 do texto com um contador até ter números suficientes.
    2. Converte cada grupo de 4 bytes num número entre -1 e 1 (4294967295 é o maior inteiro
       de 32 bits sem sinal).
    3. Corta em `dimensions` e normaliza para norma 1.
    """
    values: list[float] = []
    seed = text.encode()
    counter = 0
    # 1.
    while len(values) < dimensions:
        block = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        counter += 1
        # 2. O SHA-256 tem 32 bytes, então o `break` abaixo é só defensivo.
        for offset in range(0, len(block), 4):
            piece = block[offset : offset + 4]
            if len(piece) < 4:
                break
            raw = int.from_bytes(piece, "big")
            values.append(raw / 4294967295 * 2 - 1)
    # 3.
    selected = values[:dimensions]
    norm = math.sqrt(sum(value * value for value in selected))
    if norm == 0:
        selected[0] = 1.0
        return selected
    return [value / norm for value in selected]
