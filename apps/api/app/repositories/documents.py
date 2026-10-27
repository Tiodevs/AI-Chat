"""Documentos, versões e chunks. Seções 7.3 e 8.1 do SDD."""

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

SEED_LOCK_KEY = 32032026


@dataclass(frozen=True, slots=True)
class NewChunk:
    ordinal: int
    heading: str | None
    content: str
    embedding: list[float]


def vector_literal(values: list[float]) -> str:
    return json.dumps(values)


class SeedLock:
    """Lock de sessão. A semente atravessa várias transações. Seção 6.4."""

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def acquire(self) -> None:
        await self._connection.execute(
            text("SELECT pg_advisory_lock(:key)"),
            {"key": SEED_LOCK_KEY},
        )
        await self._connection.commit()

    async def release(self) -> None:
        await self._connection.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": SEED_LOCK_KEY},
        )
        await self._connection.commit()


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def admin_id(self) -> UUID | None:
        value = await self._session.scalar(
            text(
                "SELECT id FROM users WHERE role = 'admin' "
                "ORDER BY created_at LIMIT 1"
            )
        )
        if value is None:
            return None
        return _uuid(value)

    async def ready_checksum(self, slug: str) -> str | None:
        value = await self._session.scalar(
            text(
                "SELECT version.sha256 "
                "FROM documents AS document "
                "JOIN document_versions AS version ON version.id = document.active_version "
                "WHERE document.slug = :slug AND version.ingestion_status = 'ready'"
            ),
            {"slug": slug},
        )
        if value is None:
            return None
        return str(value)

    async def ensure_document(self, *, slug: str, title: str, created_by: UUID) -> UUID:
        existing = await self._session.scalar(
            text("SELECT id FROM documents WHERE slug = :slug"),
            {"slug": slug},
        )
        if existing is not None:
            return _uuid(existing)
        created = await self._session.scalar(
            text(
                "INSERT INTO documents (title, slug, status, created_by) "
                "VALUES (:title, :slug, 'active', :created_by) RETURNING id"
            ),
            {"title": title, "slug": slug, "created_by": created_by},
        )
        return _uuid(created)

    async def next_version(self, document_id: UUID) -> int:
        value = await self._session.scalar(
            text(
                "SELECT coalesce(max(version), 0) + 1 "
                "FROM document_versions WHERE document_id = :document_id"
            ),
            {"document_id": document_id},
        )
        return int(value or 1)

    async def insert_version(
        self,
        *,
        document_id: UUID,
        version: int,
        filename: str,
        media_type: str,
        sha256: str,
        original_bytes: bytes,
    ) -> UUID:
        created = await self._session.scalar(
            text(
                "INSERT INTO document_versions ("
                "document_id, version, filename, media_type, sha256, body_text, "
                "original_bytes, byte_size, ingestion_status"
                ") VALUES ("
                ":document_id, :version, :filename, :media_type, :sha256, '', "
                ":original_bytes, :byte_size, 'processing'"
                ") RETURNING id"
            ),
            {
                "document_id": document_id,
                "version": version,
                "filename": filename,
                "media_type": media_type,
                "sha256": sha256,
                "original_bytes": original_bytes,
                "byte_size": len(original_bytes),
            },
        )
        return _uuid(created)

    async def publish(
        self,
        *,
        document_id: UUID,
        version_id: UUID,
        title: str,
        body_text: str,
        chunks: list[NewChunk],
    ) -> None:
        for chunk in chunks:
            await self._session.execute(
                text(
                    "INSERT INTO chunks ("
                    "document_version_id, ordinal, heading, content, embedding, active"
                    ") VALUES ("
                    ":version_id, :ordinal, :heading, :content, "
                    "CAST(:embedding AS vector), false"
                    ")"
                ),
                {
                    "version_id": version_id,
                    "ordinal": chunk.ordinal,
                    "heading": chunk.heading,
                    "content": chunk.content,
                    "embedding": vector_literal(chunk.embedding),
                },
            )
        await self._session.execute(
            text(
                "UPDATE document_versions "
                "SET ingestion_status = 'ready', body_text = :body_text, error = NULL "
                "WHERE id = :version_id"
            ),
            {"version_id": version_id, "body_text": body_text},
        )
        await self._session.execute(
            text(
                "UPDATE documents "
                "SET active_version = :version_id, title = :title, updated_at = now() "
                "WHERE id = :document_id"
            ),
            {"version_id": version_id, "title": title, "document_id": document_id},
        )
        await self._session.execute(
            text(
                "UPDATE chunks SET active = false "
                "WHERE document_version_id IN ("
                "SELECT id FROM document_versions "
                "WHERE document_id = :document_id AND id <> :version_id"
                ")"
            ),
            {"document_id": document_id, "version_id": version_id},
        )
        await self._session.execute(
            text("UPDATE chunks SET active = true WHERE document_version_id = :version_id"),
            {"version_id": version_id},
        )

    async def mark_failed(self, version_id: UUID, error: str, body_text: str) -> None:
        await self._session.execute(
            text(
                "UPDATE document_versions "
                "SET ingestion_status = 'failed', error = :error, "
                "body_text = CASE WHEN :body_text = '' THEN body_text ELSE :body_text END "
                "WHERE id = :version_id AND ingestion_status = 'processing'"
            ),
            {"version_id": version_id, "error": error, "body_text": body_text},
        )

    async def fail_stale(self, deadline: datetime, error: str) -> int:
        result = await self._session.execute(
            text(
                "UPDATE document_versions "
                "SET ingestion_status = 'failed', error = :error "
                "WHERE ingestion_status = 'processing' AND created_at < :deadline"
            ),
            {"deadline": deadline, "error": error},
        )
        return int(getattr(result, "rowcount", 0) or 0)

    async def archive(self, document_id: UUID) -> None:
        await self._session.execute(
            text(
                "UPDATE documents SET status = 'archived', updated_at = now() "
                "WHERE id = :document_id"
            ),
            {"document_id": document_id},
        )

    async def id_for_slug(self, slug: str) -> UUID | None:
        value = await self._session.scalar(
            text("SELECT id FROM documents WHERE slug = :slug"),
            {"slug": slug},
        )
        if value is None:
            return None
        return _uuid(value)


def _uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
