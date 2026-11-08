"""Porta de embedding. Seção 17 do SDD.

Camada de portas. `QaWorkflow` e `RetrievalService.search` embedam a pergunta com
`embed_query`; `IngestionService` embeda os chunks com `embed_documents`. O texto já chega com
os prefixos de `app/domain/embedding_text.py`. Os adaptadores são `GeminiEmbeddingProvider`,
`DeterministicEmbeddingProvider` (testes), `LexicalEmbeddingProvider` (`demo`) e
`UnavailableEmbeddingProvider` (sem chave), escolhidos por `build_embedding_provider`.

A porta ainda não declara um tipo de erro. Os adaptadores do Gemini e o indisponível levantam
`EmbeddingRequestError`, de `app/adapters/gemini_embedding.py`, e o `QaWorkflow` importa esse
tipo do adaptador. A Etapa 13.2 do plano move o erro para a porta ou para
`app/domain/errors.py`.
"""

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Transforma texto em vetores de `dimensions` números."""

    # Nome do modelo, nos spans `qa.embed_query` e `ingestion.embed`.
    model_name: str
    # 768 na versão 1 (seção 8.3), igual à coluna `vector(768)`.
    dimensions: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Um vetor por texto, na mesma ordem.

        O `gemini-embedding-2` junta num vetor só os textos enviados juntos, então o adaptador
        do Gemini faz um pedido por texto, no máximo 4 ao mesmo tempo (seção 17).
        """
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Vetor de um texto só: a pergunta, já com o prefixo de busca."""
        ...
