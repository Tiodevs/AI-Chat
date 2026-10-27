"""Busca vetorial e por texto completo. Seções 8.2 e 8.4 do SDD."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.documents import vector_literal

_SEARCHABLE = """
document.status = 'active'
AND document.active_version = chunk.document_version_id
AND chunk.active
"""


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: UUID
    document_slug: str
    document_title: str
    heading: str | None
    content: str
    similarity: float


class RetrievalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def nearest(self, embedding: list[float], *, limit: int) -> list[RetrievedChunk]:
        rows = await self._session.execute(
            text(
                "SELECT chunk.id AS chunk_id, document.slug AS document_slug, "
                "document.title AS document_title, chunk.heading AS heading, "
                "chunk.content AS content, "
                "1 - (chunk.embedding <=> CAST(:embedding AS vector)) AS similarity "
                "FROM chunks AS chunk "
                "JOIN document_versions AS version ON version.id = chunk.document_version_id "
                "JOIN documents AS document ON document.id = version.document_id "
                f"WHERE {_SEARCHABLE} "
                "ORDER BY chunk.embedding <=> CAST(:embedding AS vector) "
                "LIMIT :limit"
            ),
            {"embedding": vector_literal(embedding), "limit": limit},
        )
        return [_chunk(dict(row)) for row in rows.mappings()]

    async def keyword(
        self,
        question: str,
        embedding: list[float],
        *,
        minimum: float,
        limit: int,
    ) -> list[RetrievedChunk]:
        rows = await self._session.execute(
            text(
                "SELECT chunk.id AS chunk_id, document.slug AS document_slug, "
                "document.title AS document_title, chunk.heading AS heading, "
                "chunk.content AS content, "
                "1 - (chunk.embedding <=> CAST(:embedding AS vector)) AS similarity "
                "FROM chunks AS chunk "
                "JOIN document_versions AS version ON version.id = chunk.document_version_id "
                "JOIN documents AS document ON document.id = version.document_id "
                f"WHERE {_SEARCHABLE} "
                "AND chunk.tsv @@ websearch_to_tsquery('portuguese', :question) "
                "AND (1 - (chunk.embedding <=> CAST(:embedding AS vector))) >= :minimum "
                "ORDER BY ts_rank("
                "chunk.tsv, websearch_to_tsquery('portuguese', :question)"
                ") DESC "
                "LIMIT :limit"
            ),
            {
                "embedding": vector_literal(embedding),
                "question": question,
                "minimum": minimum,
                "limit": limit,
            },
        )
        return [_chunk(dict(row)) for row in rows.mappings()]


def _chunk(row: dict[str, Any]) -> RetrievedChunk:
    heading = row["heading"]
    return RetrievedChunk(
        chunk_id=_uuid(row["chunk_id"]),
        document_slug=str(row["document_slug"]),
        document_title=str(row["document_title"]),
        heading=None if heading is None else str(heading),
        content=str(row["content"]),
        similarity=float(row["similarity"]),
    )


def _uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
