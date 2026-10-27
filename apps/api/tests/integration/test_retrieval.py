"""A pergunta de visita acha o chunk certo, o piso corta e o arquivo some. Seção 8.4."""

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.adapters.deterministic_embedding import DeterministicEmbeddingProvider
from app.adapters.text_extractor import FileTextExtractor
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.embedding_text import query_embedding_text
from app.repositories.documents import DocumentRepository
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService

pytestmark = pytest.mark.integration

VISITING_QUESTION = "Qual é o horário de visita?"


class _AlignedEmbedding:
    def __init__(self, visiting: list[float], other: list[float]) -> None:
        self._visiting = visiting
        self._other = other
        self.queries: list[str] = []
        self.model_name = "aligned"
        self.dimensions = len(visiting)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for piece in texts:
            if "11:00" in piece:
                vectors.append(self._visiting)
            else:
                vectors.append(self._other)
        return vectors

    async def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return self._visiting


class _SameEmbedding:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector
        self.model_name = "same"
        self.dimensions = len(vector)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector for _text in texts]

    async def embed_query(self, text: str) -> list[float]:
        del text
        return self._vector


def test_retrieval_of_visiting_hours_returns_the_visiting_chunk(
    migrated_database: str,
) -> None:
    asyncio.run(_visiting(migrated_database))


def test_retrieval_drops_keyword_matches_below_the_similarity_floor(
    migrated_database: str,
) -> None:
    asyncio.run(_floor(migrated_database))


def test_retrieval_hides_archived_documents(migrated_database: str) -> None:
    asyncio.run(_archived(migrated_database))


def test_retrieval_returns_at_most_six_chunks(migrated_database: str) -> None:
    asyncio.run(_limit(migrated_database))


async def _visiting(database_url: str) -> None:
    slug = "02-visiting"
    noise = f"noise-{uuid4().hex}"
    await _delete_slugs(database_url, [slug, noise])
    try:
        created_by = await _insert_admin(database_url)
        provider = DeterministicEmbeddingProvider()
        visiting_vector = await provider.embed_query(query_embedding_text(VISITING_QUESTION))
        other_vector = await provider.embed_query("estacionamento distante")
        embeddings = _AlignedEmbedding(visiting_vector, other_vector)
        ingestion = IngestionService(database_url, embeddings, FileTextExtractor())
        assert (
            await ingestion.ingest_new_version(
                slug=slug,
                title="Visitas",
                filename="02-visiting.md",
                media_type="text/markdown",
                data="# Visitas\n\nHorário geral de visita 11:00–20:00.\n".encode(),
                sha256="1" * 64,
                created_by=created_by,
            )
            == "embedded"
        )
        service = RetrievalService(database_url, embeddings, minimum_similarity=0.50)
        hits = await service.search(VISITING_QUESTION)
        assert embeddings.queries == [query_embedding_text(VISITING_QUESTION)]
        assert hits
        assert hits[0].document_slug == "02-visiting"
        assert len(hits) <= 6
    finally:
        await _delete_slugs(database_url, [slug, noise])


async def _floor(database_url: str) -> None:
    visiting = "02-visiting"
    noise = f"keyword-{uuid4().hex}"
    await _delete_slugs(database_url, [visiting, noise])
    try:
        created_by = await _insert_admin(database_url)
        provider = DeterministicEmbeddingProvider()
        visiting_vector = await provider.embed_query(query_embedding_text(VISITING_QUESTION))
        other_vector = await provider.embed_query("vetor distante do piso")
        embeddings = _AlignedEmbedding(visiting_vector, other_vector)
        ingestion = IngestionService(database_url, embeddings, FileTextExtractor())
        await ingestion.ingest_new_version(
            slug=visiting,
            title="Visitas",
            filename="02-visiting.md",
            media_type="text/markdown",
            data="# Visitas\n\nHorário geral de visita 11:00–20:00.\n".encode(),
            sha256="2" * 64,
            created_by=created_by,
        )
        await ingestion.ingest_new_version(
            slug=noise,
            title="Ruído",
            filename=f"{noise}.md",
            media_type="text/markdown",
            data="# Ruido\n\nQual é o horário de visita neste outro texto?\n".encode(),
            sha256="3" * 64,
            created_by=created_by,
        )
        assert await _keyword_match_count(database_url, noise, VISITING_QUESTION) == 1
        hits = await RetrievalService(
            database_url,
            embeddings,
            minimum_similarity=0.50,
        ).search(VISITING_QUESTION)
        assert [hit.document_slug for hit in hits] == ["02-visiting"]
    finally:
        await _delete_slugs(database_url, [visiting, noise])


async def _archived(database_url: str) -> None:
    slug = "02-visiting"
    await _delete_slugs(database_url, [slug])
    try:
        created_by = await _insert_admin(database_url)
        provider = DeterministicEmbeddingProvider()
        vector = await provider.embed_query(query_embedding_text(VISITING_QUESTION))
        embeddings = _SameEmbedding(vector)
        await IngestionService(database_url, embeddings, FileTextExtractor()).ingest_new_version(
            slug=slug,
            title="Visitas",
            filename="02-visiting.md",
            media_type="text/markdown",
            data="# Visitas\n\nHorário geral de visita 11:00–20:00.\n".encode(),
            sha256="4" * 64,
            created_by=created_by,
        )
        async with open_session(database_url) as session, UnitOfWork(session):
            repository = DocumentRepository(session)
            document_id = await repository.id_for_slug(slug)
            assert document_id is not None
            await repository.archive(document_id)
        hits = await RetrievalService(
            database_url,
            embeddings,
            minimum_similarity=0.50,
        ).search(VISITING_QUESTION)
        assert all(hit.document_slug != slug for hit in hits)
    finally:
        await _delete_slugs(database_url, [slug])


async def _limit(database_url: str) -> None:
    slug = f"many-{uuid4().hex}"
    await _delete_slugs(database_url, [slug])
    try:
        created_by = await _insert_admin(database_url)
        question = "Quantos resultados cabem?"
        provider = DeterministicEmbeddingProvider()
        vector = await provider.embed_query(query_embedding_text(question))
        sections = "\n\n".join(f"# Parte {index}\n\nTexto distinto {index}." for index in range(8))
        await IngestionService(
            database_url,
            _SameEmbedding(vector),
            FileTextExtractor(),
        ).ingest_new_version(
            slug=slug,
            title="Muitos",
            filename=f"{slug}.md",
            media_type="text/markdown",
            data=sections.encode(),
            sha256="5" * 64,
            created_by=created_by,
        )
        hits = await RetrievalService(
            database_url,
            _SameEmbedding(vector),
            minimum_similarity=0.50,
        ).search(question)
        assert len(hits) == 6
    finally:
        await _delete_slugs(database_url, [slug])


async def _insert_admin(database_url: str) -> UUID:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            created = await connection.scalar(
                text(
                    "INSERT INTO users (email, password_hash, full_name, role) "
                    "VALUES (:email, 'hash', 'Admin', 'admin') RETURNING id"
                ),
                {"email": f"retrieval-{uuid4().hex}@example.com"},
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


async def _keyword_match_count(database_url: str, slug: str, question: str) -> int:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            count = await connection.scalar(
                text(
                    "SELECT count(*) FROM chunks AS chunk "
                    "JOIN documents AS document "
                    "ON document.active_version = chunk.document_version_id "
                    "WHERE document.slug = :slug AND chunk.active "
                    "AND chunk.tsv @@ websearch_to_tsquery('portuguese', :question)"
                ),
                {"slug": slug, "question": question},
            )
    finally:
        await engine.dispose()
    return int(count or 0)
