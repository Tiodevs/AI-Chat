"""Chunk recuperado. Sem I/O. Seção 8.4 do SDD.

Camada de domínio. `RetrievalRepository` monta cada `RetrievedChunk` a partir do SQL; a porta
`HybridSearch` e o `RetrievalService` os devolvem; o `QaWorkflow` os transforma em blocos de
contexto e em entrada do rastro, e o script `search` os imprime.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """Um chunk pesquisável e a similaridade de cosseno dele com a pergunta.

    Pesquisável quer dizer documento ativo, versão ativa e chunk ativo (seção 8.2).
    `similarity` é `1 - distância` do pgvector (seção 8.3), e `RETRIEVAL_MIN_SIMILARITY` corta
    os fracos. Um chunk que veio da busca por palavra-chave também traz a similaridade,
    calculada com o mesmo vetor da pergunta.
    """

    chunk_id: UUID
    document_slug: str
    document_title: str
    heading: str | None
    content: str
    similarity: float
