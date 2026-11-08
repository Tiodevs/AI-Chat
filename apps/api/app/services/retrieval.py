"""Busca híbrida: vetor, texto e fusão. Seção 8.4 do SDD.

Camada de serviço. `RetrievalService` implementa a porta `HybridSearch`
(`app/ports/search.py`), que o `QaWorkflow` recebe pelo construtor em
`core/container.py:build_ai_runtime`. Os scripts `scripts/search.py`, `scripts/ask.py` e
`scripts/run_evals.py` também o montam. Usa `RetrievalRepository`, que aplica o predicado de
chunk pesquisável da seção 8.2, e a fusão pura `domain/ranking.py:reciprocal_rank_fusion`.

O embedding da pergunta acontece antes da transação: no workflow, que já embedou dentro do
span `qa.embed_query`, ou em `search`. A busca em si é uma transação curta de leitura.
"""

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.embedding_text import query_embedding_text
from app.domain.ranking import (
    KEYWORD_CANDIDATES,
    RESULT_LIMIT,
    VECTOR_CANDIDATES,
    reciprocal_rank_fusion,
)
from app.ports.embedding import EmbeddingProvider
from app.repositories.retrieval import RetrievalRepository, RetrievedChunk


class RetrievalService:
    """Recupera até 6 chunks ativos para uma pergunta.

    `minimum_similarity` é o piso `RETRIEVAL_MIN_SIMILARITY` (padrão 0,50, seção 7.1). O
    workflow recebe o mesmo valor e o aplica de novo antes de montar o contexto.
    """

    def __init__(
        self,
        database_url: str,
        embeddings: EmbeddingProvider,
        *,
        minimum_similarity: float,
    ) -> None:
        self._database_url = database_url
        self._embeddings = embeddings
        self._minimum_similarity = minimum_similarity

    async def search(self, question: str) -> list[RetrievedChunk]:
        """Embeda a pergunta com o prefixo da seção 8.3 e busca.

        Usado pelo script de busca. Chama o provedor de embedding, pela rede, antes de abrir
        a transação.
        """
        vector = await self._embeddings.embed_query(query_embedding_text(question))
        return await self.search_by_vector(question, vector)

    async def search_by_vector(self, question: str, embedding: list[float]) -> list[RetrievedChunk]:
        """Os passos 1 a 5 da seção 8.4 para uma pergunta já embedada.

        1. Os 20 chunks ativos mais próximos pela distância de cosseno.
        2. Descarta os que ficam abaixo do piso de similaridade.
        3. Até 20 chunks que casam com `websearch_to_tsquery('portuguese', question)`, já
           filtrados pelo piso no SQL: a palavra-chave não admite um chunk que falhou nele.
        4. Funde as duas listas por reciprocal rank fusion, constante 60.
        5. Devolve os 6 primeiros.

        `question` é o texto da busca por palavra, a pergunta autônoma da reescrita quando
        quem chama é o workflow. Só voltam candidatos acima do piso, então a métrica
        `atrium_qa_top_similarity` não vê a melhor similaridade abaixo dele (Etapa 13.5).
        """
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = RetrievalRepository(session)
            # 1.
            nearest = await repository.nearest(embedding, limit=VECTOR_CANDIDATES)
            # 2.
            vector_hits = [hit for hit in nearest if hit.similarity >= self._minimum_similarity]
            # 3.
            keyword_hits = await repository.keyword(
                question,
                embedding,
                minimum=self._minimum_similarity,
                limit=KEYWORD_CANDIDATES,
            )
        # Um chunk nas duas listas aparece uma vez; o resultado vetorial fica no lugar dele.
        by_id = {hit.chunk_id: hit for hit in vector_hits}
        for hit in keyword_hits:
            by_id.setdefault(hit.chunk_id, hit)
        # 4. A fusão é uma função pura do domínio, testada sem banco.
        ordered = reciprocal_rank_fusion(
            [
                [hit.chunk_id for hit in vector_hits],
                [hit.chunk_id for hit in keyword_hits],
            ]
        )
        # 5.
        return [by_id[chunk_id] for chunk_id in ordered[:RESULT_LIMIT]]
