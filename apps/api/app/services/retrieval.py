"""Busca híbrida: vetor, texto e fusão. Seção 8.4 do SDD."""

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
        vector = await self._embeddings.embed_query(query_embedding_text(question))
        async with open_session(self._database_url) as session, UnitOfWork(session):
            repository = RetrievalRepository(session)
            nearest = await repository.nearest(vector, limit=VECTOR_CANDIDATES)
            vector_hits = [hit for hit in nearest if hit.similarity >= self._minimum_similarity]
            keyword_hits = await repository.keyword(
                question,
                vector,
                minimum=self._minimum_similarity,
                limit=KEYWORD_CANDIDATES,
            )
        by_id = {hit.chunk_id: hit for hit in vector_hits}
        for hit in keyword_hits:
            by_id.setdefault(hit.chunk_id, hit)
        ordered = reciprocal_rank_fusion(
            [
                [hit.chunk_id for hit in vector_hits],
                [hit.chunk_id for hit in keyword_hits],
            ]
        )
        return [by_id[chunk_id] for chunk_id in ordered[:RESULT_LIMIT]]
