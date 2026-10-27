"""Chunk recuperado. Sem I/O. Seção 8.4 do SDD."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: UUID
    document_slug: str
    document_title: str
    heading: str | None
    content: str
    similarity: float
