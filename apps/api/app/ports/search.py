"""Busca híbrida vista pelo workflow, sem sessão. Seção 8.4 do SDD.

Camada de portas. O `QaWorkflow` não abre sessão de banco (seção 6.2): ele recebe esta porta, e
a implementação, `RetrievalService` (`app/services/retrieval.py`), abre a própria transação
curta, busca por vetor e por texto completo e funde as duas listas com
`reciprocal_rank_fusion`. A raiz de composição monta o `RetrievalService` no `AiRuntime`; os
testes de unidade passam uma busca falsa.
"""

from collections.abc import Sequence
from typing import Protocol

from app.domain.retrieval import RetrievedChunk


class HybridSearch(Protocol):
    """Os chunks pesquisáveis mais relevantes para uma pergunta, já fundidos e cortados."""

    async def search_by_vector(
        self,
        question: str,
        embedding: list[float],
    ) -> Sequence[RetrievedChunk]:
        """Busca com o vetor da pergunta já calculado.

        `question` vai para a busca por texto completo, e `embedding` para a busca vetorial e
        para o piso de similaridade. Devolve até `RESULT_LIMIT` chunks, do mais relevante ao
        menos relevante.
        """
        ...
