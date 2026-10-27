"""Semente idempotente, falha de versão, prefixos e ingestão presa. Seções 6.4 e 7.3."""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.adapters.deterministic_embedding import DeterministicEmbeddingProvider
from app.adapters.text_extractor import FileTextExtractor
from app.core.container import get_settings
from app.domain.embedding_text import document_embedding_text
from app.main import create_app
from app.prompts.corpus import EMPTY_DOCUMENT, PROCESSING_TIMED_OUT
from app.services.ingestion import IngestionService, fail_stale_processing_versions
from app.services.seed import SeedService

pytestmark = pytest.mark.integration


class _Clock:
    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment


class _CountingEmbedding:
    def __init__(self) -> None:
        self.calls = 0
        self.texts: list[str] = []
        self._inner = DeterministicEmbeddingProvider()
        self.model_name = self._inner.model_name
        self.dimensions = self._inner.dimensions

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.texts.extend(texts)
        return await self._inner.embed_documents(texts)

    async def embed_query(self, text: str) -> list[float]:
        return await self._inner.embed_query(text)


class _FailingEmbedding:
    model_name = "failing"
    dimensions = 768

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        del texts
        raise RuntimeError("embedding failed")

    async def embed_query(self, text: str) -> list[float]:
        del text
        raise RuntimeError("embedding failed")


def test_seed_embeds_once_and_concurrent_runs_do_not_duplicate(
    migrated_database: str,
    tmp_path: Path,
) -> None:
    asyncio.run(_seed_once(migrated_database, tmp_path))


def test_failed_new_version_leaves_previous_chunks_searchable(migrated_database: str) -> None:
    asyncio.run(_failed_version(migrated_database))


def test_embedding_prefixes_are_sent_and_not_stored(migrated_database: str) -> None:
    asyncio.run(_prefixes(migrated_database))


def test_empty_document_is_not_embedded(migrated_database: str) -> None:
    asyncio.run(_empty(migrated_database))


def test_stale_processing_versions_fail_on_startup(migrated_database: str) -> None:
    asyncio.run(_stale(migrated_database))


def test_app_startup_fails_a_stale_processing_version(
    migrated_database: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database)
    get_settings.cache_clear()
    slug = f"startup-{uuid4().hex}"

    async def prepare() -> UUID:
        created_by = await _insert_admin(migrated_database)
        old_id, _recent_id = await _insert_processing_pair(
            migrated_database,
            slug,
            created_by,
            datetime.now(UTC),
        )
        return old_id

    old_id = asyncio.run(prepare())
    try:
        with TestClient(create_app()) as client:
            assert client.get("/health").status_code == 200
        assert asyncio.run(_version_status(migrated_database, old_id)) == "failed"
        assert asyncio.run(_version_error(migrated_database, old_id)) == PROCESSING_TIMED_OUT
    finally:
        asyncio.run(_delete_slugs(migrated_database, [slug]))


async def _seed_once(database_url: str, directory: Path) -> None:
    (directory / "01-um.md").write_text("# Um\n\nTexto um do hospital.\n", encoding="utf-8")
    (directory / "02-dois.md").write_text("# Dois\n\nTexto dois do hospital.\n", encoding="utf-8")
    slugs = ["01-um", "02-dois"]
    await _delete_slugs(database_url, slugs)
    try:
        admin_id = await _insert_admin(database_url)
        del admin_id
        embeddings = _CountingEmbedding()
        service = _seed_service(database_url, directory, embeddings)
        first = await service.run()
        calls_after_first = embeddings.calls
        assert first.embedded == 2
        assert calls_after_first == 2
        second = await service.run()
        assert second.embedded == 0
        assert second.unchanged == 2
        assert embeddings.calls == calls_after_first
        await _delete_slugs(database_url, slugs)
        embeddings.calls = 0
        await asyncio.gather(service.run(), service.run())
        assert embeddings.calls == 2
        assert await _version_count(database_url, slugs) == 2
    finally:
        await _delete_slugs(database_url, slugs)


async def _failed_version(database_url: str) -> None:
    slug = f"stable-{uuid4().hex}"
    await _delete_slugs(database_url, [slug])
    try:
        created_by = await _insert_admin(database_url)
        first = _ingestion(database_url, _CountingEmbedding())
        outcome = await first.ingest_new_version(
            slug=slug,
            title="Estável",
            filename=f"{slug}.md",
            media_type="text/markdown",
            data=b"# Estavel\n\nHorario de visita estavel.\n",
            sha256="a" * 64,
            created_by=created_by,
        )
        assert outcome == "embedded"
        second = _ingestion(database_url, _FailingEmbedding())
        failed = await second.ingest_new_version(
            slug=slug,
            title="Estável",
            filename=f"{slug}.md",
            media_type="text/markdown",
            data=b"# Estavel\n\nTexto novo que nao pode substituir.\n",
            sha256="b" * 64,
            created_by=created_by,
        )
        assert failed == "failed"
        contents = await _active_contents(database_url, slug)
        assert contents == ["Horario de visita estavel."]
        assert await _latest_status(database_url, slug) == "failed"
    finally:
        await _delete_slugs(database_url, [slug])


async def _prefixes(database_url: str) -> None:
    slug = f"prefix-{uuid4().hex}"
    await _delete_slugs(database_url, [slug])
    try:
        created_by = await _insert_admin(database_url)
        embeddings = _CountingEmbedding()
        outcome = await _ingestion(database_url, embeddings).ingest_new_version(
            slug=slug,
            title="Visitas",
            filename=f"{slug}.md",
            media_type="text/markdown",
            data="# Visitas\n\nHorário geral de visita.\n".encode(),
            sha256="c" * 64,
            created_by=created_by,
        )
        assert outcome == "embedded"
        assert embeddings.texts == [
            document_embedding_text("Visitas", "Visitas", "Horário geral de visita.")
        ]
        stored = await _active_contents(database_url, slug)
        assert stored == ["Horário geral de visita."]
        assert not stored[0].startswith("title:")
    finally:
        await _delete_slugs(database_url, [slug])


async def _empty(database_url: str) -> None:
    slug = f"empty-{uuid4().hex}"
    await _delete_slugs(database_url, [slug])
    try:
        created_by = await _insert_admin(database_url)
        embeddings = _CountingEmbedding()
        outcome = await _ingestion(database_url, embeddings).ingest_new_version(
            slug=slug,
            title="Vazio",
            filename=f"{slug}.md",
            media_type="text/markdown",
            data=b" \n",
            sha256="d" * 64,
            created_by=created_by,
        )
        assert outcome == "failed"
        assert embeddings.calls == 0
        assert await _latest_error(database_url, slug) == EMPTY_DOCUMENT
    finally:
        await _delete_slugs(database_url, [slug])


async def _stale(database_url: str) -> None:
    slug = f"stale-{uuid4().hex}"
    await _delete_slugs(database_url, [slug])
    try:
        created_by = await _insert_admin(database_url)
        now = datetime.now(UTC)
        old_id, recent_id = await _insert_processing_pair(database_url, slug, created_by, now)
        changed = await fail_stale_processing_versions(database_url, _Clock(now))
        assert changed >= 1
        assert await _version_status(database_url, old_id) == "failed"
        assert await _version_error(database_url, old_id) == PROCESSING_TIMED_OUT
        assert await _version_status(database_url, recent_id) == "processing"
    finally:
        await _delete_slugs(database_url, [slug])


def _seed_service(
    database_url: str,
    directory: Path,
    embeddings: _CountingEmbedding,
) -> SeedService:
    ingestion = _ingestion(database_url, embeddings)
    return SeedService(database_url, ingestion, directory)


def _ingestion(database_url: str, embeddings: object) -> IngestionService:
    return IngestionService(database_url, embeddings, FileTextExtractor())  # type: ignore[arg-type]


async def _insert_admin(database_url: str) -> UUID:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            created = await connection.scalar(
                text(
                    "INSERT INTO users (email, password_hash, full_name, role) "
                    "VALUES (:email, 'hash', 'Admin', 'admin') RETURNING id"
                ),
                {"email": f"seed-{uuid4().hex}@example.com"},
            )
    finally:
        await engine.dispose()
    assert isinstance(created, UUID)
    return created


async def _delete_slugs(database_url: str, slugs: list[str]) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            for slug in slugs:
                await connection.execute(
                    text("UPDATE documents SET active_version = NULL WHERE slug = :slug"),
                    {"slug": slug},
                )
                await connection.execute(
                    text(
                        "DELETE FROM chunks WHERE document_version_id IN ("
                        "SELECT version.id FROM document_versions AS version "
                        "JOIN documents AS document ON document.id = version.document_id "
                        "WHERE document.slug = :slug)"
                    ),
                    {"slug": slug},
                )
                await connection.execute(
                    text(
                        "DELETE FROM document_versions WHERE document_id IN ("
                        "SELECT id FROM documents WHERE slug = :slug)"
                    ),
                    {"slug": slug},
                )
                await connection.execute(
                    text("DELETE FROM documents WHERE slug = :slug"),
                    {"slug": slug},
                )
    finally:
        await engine.dispose()


async def _version_count(database_url: str, slugs: list[str]) -> int:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            total = 0
            for slug in slugs:
                count = await connection.scalar(
                    text(
                        "SELECT count(*) FROM document_versions AS version "
                        "JOIN documents AS document ON document.id = version.document_id "
                        "WHERE document.slug = :slug"
                    ),
                    {"slug": slug},
                )
                total += int(count or 0)
            return total
    finally:
        await engine.dispose()


async def _active_contents(database_url: str, slug: str) -> list[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "SELECT chunk.content FROM chunks AS chunk "
                    "JOIN documents AS document "
                    "ON document.active_version = chunk.document_version_id "
                    "WHERE document.slug = :slug AND document.status = 'active' "
                    "AND chunk.active ORDER BY chunk.ordinal"
                ),
                {"slug": slug},
            )
            return [str(row[0]) for row in rows]
    finally:
        await engine.dispose()


async def _latest_status(database_url: str, slug: str) -> str:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            status = await connection.scalar(
                text(
                    "SELECT version.ingestion_status FROM document_versions AS version "
                    "JOIN documents AS document ON document.id = version.document_id "
                    "WHERE document.slug = :slug ORDER BY version.version DESC LIMIT 1"
                ),
                {"slug": slug},
            )
    finally:
        await engine.dispose()
    return str(status)


async def _latest_error(database_url: str, slug: str) -> str:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            error = await connection.scalar(
                text(
                    "SELECT version.error FROM document_versions AS version "
                    "JOIN documents AS document ON document.id = version.document_id "
                    "WHERE document.slug = :slug ORDER BY version.version DESC LIMIT 1"
                ),
                {"slug": slug},
            )
    finally:
        await engine.dispose()
    return str(error)


async def _insert_processing_pair(
    database_url: str,
    slug: str,
    created_by: UUID,
    now: datetime,
) -> tuple[UUID, UUID]:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            document_id = await connection.scalar(
                text(
                    "INSERT INTO documents (title, slug, status, created_by) "
                    "VALUES ('Presa', :slug, 'active', :created_by) RETURNING id"
                ),
                {"slug": slug, "created_by": created_by},
            )
            old_id = await connection.scalar(
                text(
                    "INSERT INTO document_versions ("
                    "document_id, version, filename, media_type, sha256, body_text, "
                    "original_bytes, byte_size, ingestion_status, created_at"
                    ") VALUES ("
                    ":document_id, 1, 'old.md', 'text/markdown', :sha256, '', "
                    ":original_bytes, 1, 'processing', :created_at"
                    ") RETURNING id"
                ),
                {
                    "document_id": document_id,
                    "sha256": "e" * 64,
                    "original_bytes": b"x",
                    "created_at": now - timedelta(minutes=16),
                },
            )
            recent_id = await connection.scalar(
                text(
                    "INSERT INTO document_versions ("
                    "document_id, version, filename, media_type, sha256, body_text, "
                    "original_bytes, byte_size, ingestion_status, created_at"
                    ") VALUES ("
                    ":document_id, 2, 'new.md', 'text/markdown', :sha256, '', "
                    ":original_bytes, 1, 'processing', :created_at"
                    ") RETURNING id"
                ),
                {
                    "document_id": document_id,
                    "sha256": "f" * 64,
                    "original_bytes": b"y",
                    "created_at": now - timedelta(minutes=1),
                },
            )
    finally:
        await engine.dispose()
    assert isinstance(old_id, UUID)
    assert isinstance(recent_id, UUID)
    return old_id, recent_id


async def _version_status(database_url: str, version_id: UUID) -> str:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            status = await connection.scalar(
                text("SELECT ingestion_status FROM document_versions WHERE id = :version_id"),
                {"version_id": version_id},
            )
    finally:
        await engine.dispose()
    return str(status)


async def _version_error(database_url: str, version_id: UUID) -> str:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            error = await connection.scalar(
                text("SELECT error FROM document_versions WHERE id = :version_id"),
                {"version_id": version_id},
            )
    finally:
        await engine.dispose()
    return str(error)
