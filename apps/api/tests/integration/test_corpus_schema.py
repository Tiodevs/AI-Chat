"""Esquema do corpus: vector(768), tsv em português e índices da seção 8.2."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

pytestmark = pytest.mark.integration

EXPECTED_INDEXES = {
    "chunks_embedding_idx": ("hnsw", "vector_cosine_ops", True),
    "chunks_tsv_idx": ("gin", None, True),
    "document_versions_document_id_idx": ("btree", None, False),
}


def test_section_8_2_indexes_exist_for_the_corpus_tables(migrated_database: str) -> None:
    asyncio.run(_assert_indexes(migrated_database))


def test_chunks_store_vector_768_and_portuguese_tsv(migrated_database: str) -> None:
    asyncio.run(_assert_vector_and_tsv(migrated_database))


async def _assert_indexes(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT index_name.relname, access_method.amname, "
                        "pg_get_indexdef(index.indexrelid) "
                        "FROM pg_index AS index "
                        "JOIN pg_class AS index_name ON index_name.oid = index.indexrelid "
                        "JOIN pg_class AS table_name ON table_name.oid = index.indrelid "
                        "JOIN pg_namespace AS namespace "
                        "ON namespace.oid = table_name.relnamespace "
                        "JOIN pg_am AS access_method ON access_method.oid = index_name.relam "
                        "WHERE namespace.nspname = 'public' "
                        "AND index_name.relname = ANY(:names)"
                    ),
                    {"names": list(EXPECTED_INDEXES)},
                )
            ).all()
    finally:
        await engine.dispose()

    found = {str(name): (str(method), str(definition)) for name, method, definition in rows}
    assert set(found) == set(EXPECTED_INDEXES)
    for name, (method, operator, partial) in EXPECTED_INDEXES.items():
        access_method, definition = found[name]
        assert access_method == method
        if operator is not None:
            assert operator in definition
        where = definition.split(" WHERE ", 1)
        if partial:
            assert where[1].strip() in {"(active)", "active"}
        else:
            assert len(where) == 1


async def _assert_vector_and_tsv(database_url: str) -> None:
    engine = create_async_engine(database_url)
    suffix = uuid4().hex
    try:
        async with engine.connect() as connection:
            embedding_type = await connection.scalar(
                text(
                    "SELECT format_type(attribute.atttypid, attribute.atttypmod) "
                    "FROM pg_attribute AS attribute "
                    "JOIN pg_class AS table_name ON table_name.oid = attribute.attrelid "
                    "JOIN pg_namespace AS namespace ON namespace.oid = table_name.relnamespace "
                    "WHERE namespace.nspname = 'public' "
                    "AND table_name.relname = 'chunks' "
                    "AND attribute.attname = 'embedding'"
                )
            )
            generated = (
                await connection.execute(
                    text(
                        "SELECT is_generated, generation_expression "
                        "FROM information_schema.columns "
                        "WHERE table_schema = 'public' "
                        "AND table_name = 'chunks' AND column_name = 'tsv'"
                    )
                )
            ).one()
        assert embedding_type == "vector(768)"
        assert generated[0] == "ALWAYS"
        expression = str(generated[1])
        assert "portuguese" in expression
        assert "heading" in expression
        assert "content" in expression
        await _exercise_corpus_rows(engine, suffix)
    finally:
        await engine.dispose()


async def _exercise_corpus_rows(engine: AsyncEngine, suffix: str) -> None:
    email = f"corpus-{suffix}@example.com"
    slug = f"visiting-{suffix}"
    async with engine.begin() as connection:
        user_id = await connection.scalar(
            text(
                "INSERT INTO users (email, password_hash, full_name, role) "
                "VALUES (:email, 'hash', 'Visitor', 'member') RETURNING id"
            ),
            {"email": email},
        )
        document_id = await connection.scalar(
            text(
                "INSERT INTO documents (title, slug, status, created_by) "
                "VALUES ('Visitas', :slug, 'active', :user_id) RETURNING id"
            ),
            {"slug": slug, "user_id": user_id},
        )
        version_id = await connection.scalar(
            text(
                "INSERT INTO document_versions ("
                "document_id, version, filename, media_type, sha256, body_text, "
                "original_bytes, byte_size, ingestion_status"
                ") VALUES ("
                ":document_id, 1, '02-visiting.md', 'text/markdown', :sha256, "
                ":body_text, :original_bytes, :byte_size, 'ready'"
                ") RETURNING id"
            ),
            {
                "document_id": document_id,
                "sha256": "ab" * 32,
                "body_text": "Horário geral de visita",
                "original_bytes": b"Horario",
                "byte_size": 7,
            },
        )
        await connection.execute(
            text("UPDATE documents SET active_version = :version_id WHERE id = :document_id"),
            {"version_id": version_id, "document_id": document_id},
        )
        matches = await connection.scalar(
            text(
                "INSERT INTO chunks ("
                "document_version_id, ordinal, heading, content, embedding, active"
                ") VALUES ("
                ":version_id, 0, 'Visitas', 'Horário geral de visita', "
                "array_fill(0.1, ARRAY[768])::vector(768), true"
                ") RETURNING tsv @@ to_tsquery('portuguese', 'visita')"
            ),
            {"version_id": version_id},
        )
        assert matches is True

    async with engine.connect() as connection:
        with pytest.raises(IntegrityError):
            async with connection.begin():
                await connection.execute(
                    text(
                        "INSERT INTO documents (title, slug, status, created_by) "
                        "VALUES ('Rascunho', :slug, 'draft', :user_id)"
                    ),
                    {"slug": f"draft-{suffix}", "user_id": user_id},
                )
        with pytest.raises(IntegrityError):
            async with connection.begin():
                await connection.execute(
                    text(
                        "INSERT INTO document_versions ("
                        "document_id, version, filename, media_type, sha256, body_text, "
                        "original_bytes, byte_size, ingestion_status"
                        ") VALUES ("
                        ":document_id, 1, '02-visiting.md', 'text/markdown', :sha256, "
                        "'outra', :original_bytes, 5, 'processing'"
                        ")"
                    ),
                    {
                        "document_id": document_id,
                        "sha256": "cd" * 32,
                        "original_bytes": b"outra",
                    },
                )
        with pytest.raises(DBAPIError, match="768"):
            async with connection.begin():
                await connection.execute(
                    text(
                        "INSERT INTO chunks ("
                        "document_version_id, ordinal, heading, content, embedding, active"
                        ") VALUES ("
                        ":version_id, 1, NULL, 'curto', "
                        "array_fill(0.1, ARRAY[3])::vector(768), false"
                        ")"
                    ),
                    {"version_id": version_id},
                )
