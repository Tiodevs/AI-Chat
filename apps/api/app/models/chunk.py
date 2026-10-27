"""Tabela chunks. Seções 8.1 e 8.2 do SDD."""

import uuid

from sqlalchemy import Boolean, Computed, ForeignKey, Index, Integer, Text, Uuid, text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.vector import EMBEDDING_DIMENSIONS, Vector

CHUNK_TSV_EXPRESSION = "to_tsvector('portuguese', coalesce(heading, '') || ' ' || content)"


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index(
            "chunks_embedding_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=text("active"),
        ),
        Index(
            "chunks_tsv_idx",
            "tsv",
            postgresql_using="gin",
            postgresql_where=text("active"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_versions.id"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    tsv: Mapped[str] = mapped_column(
        TSVECTOR(),
        Computed(CHUNK_TSV_EXPRESSION, persisted=True),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False)
