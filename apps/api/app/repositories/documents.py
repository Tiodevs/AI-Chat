"""Documentos, versões e chunks. Seções 7.3 e 8.1 do SDD."""

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.domain.documents import DocumentView, StoredVersion, VersionView

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

    async def list_views(self) -> list[DocumentView]:
        """Ativos primeiro, depois os arquivados, do mais recente ao mais antigo."""
        result = await self._session.execute(text(_VIEW_SQL + _VIEW_ORDER))
        return [_view(row) for row in result.mappings()]

    async def view(self, document_id: UUID) -> DocumentView | None:
        result = await self._session.execute(
            text(_VIEW_SQL + " WHERE document.id = :document_id"),
            {"document_id": document_id},
        )
        row = result.mappings().first()
        return None if row is None else _view(row)

    async def lock(self, document_id: UUID) -> tuple[str, str, str] | None:
        """Trava o documento para a ação do admin. Devolve slug, título e status."""
        result = await self._session.execute(
            text(
                "SELECT slug, title, status FROM documents "
                "WHERE id = :document_id FOR UPDATE"
            ),
            {"document_id": document_id},
        )
        row = result.first()
        if row is None:
            return None
        return str(row[0]), str(row[1]), str(row[2])

    async def taken_slugs(self, base: str) -> set[str]:
        """O slug vem de slugify, então só tem letras, dígitos e hífens."""
        result = await self._session.execute(
            text("SELECT slug FROM documents WHERE slug = :base OR slug LIKE :pattern"),
            {"base": base, "pattern": base + "-%"},
        )
        return {str(value) for value in result.scalars()}

    async def create_document(self, *, slug: str, title: str, created_by: UUID) -> UUID:
        created = await self._session.scalar(
            text(
                "INSERT INTO documents (title, slug, status, created_by) "
                "VALUES (:title, :slug, 'active', :created_by) RETURNING id"
            ),
            {"title": title, "slug": slug, "created_by": created_by},
        )
        return _uuid(created)

    async def touch(self, document_id: UUID) -> None:
        await self._session.execute(
            text("UPDATE documents SET updated_at = now() WHERE id = :document_id"),
            {"document_id": document_id},
        )

    async def latest_stored(self, document_id: UUID) -> StoredVersion | None:
        result = await self._session.execute(
            text(
                "SELECT id, filename, media_type, sha256, ingestion_status, created_at, "
                "original_bytes FROM document_versions "
                "WHERE document_id = :document_id ORDER BY version DESC LIMIT 1"
            ),
            {"document_id": document_id},
        )
        row = result.mappings().first()
        if row is None:
            return None
        return StoredVersion(
            id=_uuid(row["id"]),
            filename=str(row["filename"]),
            media_type=str(row["media_type"]),
            sha256=str(row["sha256"]),
            ingestion_status=str(row["ingestion_status"]),
            created_at=row["created_at"],
            original_bytes=bytes(row["original_bytes"]),
        )

    async def processing_since(self, document_id: UUID) -> list[datetime]:
        result = await self._session.execute(
            text(
                "SELECT created_at FROM document_versions "
                "WHERE document_id = :document_id AND ingestion_status = 'processing'"
            ),
            {"document_id": document_id},
        )
        return list(result.scalars())

    async def id_for_slug(self, slug: str) -> UUID | None:
        value = await self._session.scalar(
            text("SELECT id FROM documents WHERE slug = :slug"),
            {"slug": slug},
        )
        if value is None:
            return None
        return _uuid(value)


_VERSION_COLUMNS = (
    "id", "version", "filename", "media_type", "byte_size",
    "ingestion_status", "error", "created_at",
)


def _version_select(alias: str, prefix: str) -> str:
    return ", ".join(f"{alias}.{column} AS {prefix}_{column}" for column in _VERSION_COLUMNS)


_VIEW_SQL = (
    "SELECT document.id, document.title, document.slug, document.status, "
    "document.created_at, document.updated_at, "
    + _version_select("active", "active")
    + ", "
    + _version_select("latest", "latest")
    + " FROM documents AS document "
    "LEFT JOIN document_versions AS active ON active.id = document.active_version "
    "LEFT JOIN LATERAL ("
    "SELECT * FROM document_versions AS candidate "
    "WHERE candidate.document_id = document.id "
    "ORDER BY candidate.version DESC LIMIT 1"
    ") AS latest ON true"
)
_VIEW_ORDER = " ORDER BY document.status = 'archived', document.updated_at DESC, document.title"


def _version(row: RowMapping, prefix: str) -> VersionView | None:
    if row[f"{prefix}_id"] is None:
        return None
    error = row[f"{prefix}_error"]
    return VersionView(
        id=_uuid(row[f"{prefix}_id"]),
        version=int(row[f"{prefix}_version"]),
        filename=str(row[f"{prefix}_filename"]),
        media_type=str(row[f"{prefix}_media_type"]),
        byte_size=int(row[f"{prefix}_byte_size"]),
        ingestion_status=str(row[f"{prefix}_ingestion_status"]),
        error=None if error is None else str(error),
        created_at=row[f"{prefix}_created_at"],
    )


def _view(row: RowMapping) -> DocumentView:
    return DocumentView(
        id=_uuid(row["id"]),
        title=str(row["title"]),
        slug=str(row["slug"]),
        status=str(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        active_version=_version(row, "active"),
        latest_version=_version(row, "latest"),
    )


def _uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))
