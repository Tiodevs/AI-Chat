import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.container import get_settings
from app.main import create_app
from app.models import Base
from tests.integration.conftest import integration_database_url

pytestmark = pytest.mark.integration


def test_remote_database_url_is_ignored() -> None:
    assert integration_database_url("") is None
    assert integration_database_url("postgresql://user:secret@db.example:5432/railway") is None
    local = integration_database_url("postgresql://localhost:5432/atrium")
    assert local == "postgresql+asyncpg://localhost:5432/atrium"

EXPECTED_COLUMNS: dict[str, set[str]] = {
    "users": {
        "id",
        "email",
        "password_hash",
        "full_name",
        "phone",
        "visitor_type",
        "visit_reason",
        "role",
        "last_seen_at",
        "created_at",
        "updated_at",
    },
    "auth_sessions": {
        "id",
        "token_hash",
        "user_id",
        "expires_at",
        "revoked_at",
        "user_agent",
    },
    "rate_limit_windows": {"bucket_key", "window_start", "count"},
    "audit_events": {
        "id",
        "actor_user_id",
        "action",
        "target_type",
        "target_id",
        "reason",
        "created_at",
    },
}

EXPECTED_CONSTRAINTS: dict[str, set[str]] = {
    "users": {
        "users_pkey",
        "users_email_key",
        "users_email_lowercase",
        "users_role",
        "users_visitor_type",
    },
    "auth_sessions": {
        "auth_sessions_pkey",
        "auth_sessions_token_hash_key",
        "auth_sessions_user_id_fkey",
    },
    "rate_limit_windows": {"rate_limit_windows_pkey"},
    "audit_events": {"audit_events_pkey", "audit_events_actor_user_id_fkey"},
}


def test_migration_creates_the_extension_and_tables(migrated_database: str) -> None:
    asyncio.run(_assert_schema(migrated_database))


def test_ready_returns_200_when_the_database_is_up(migrated_database: str) -> None:
    del migrated_database
    get_settings.cache_clear()
    response = TestClient(create_app()).get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


def test_ready_fails_without_the_vector_extension(
    migrated_database: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    asyncio.run(_set_vector_extension(migrated_database, present=False))
    try:
        get_settings.cache_clear()
        response = TestClient(create_app()).get("/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unavailable"}
        output = capsys.readouterr().out
        events = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
        reasons = [
            event.get("reason") for event in events if event.get("event") == "readiness.failed"
        ]
        assert reasons == ["vector_missing"]
    finally:
        asyncio.run(_set_vector_extension(migrated_database, present=True))


async def _assert_schema(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            extension = await connection.scalar(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
            )
            assert extension == 1
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == "0001_initial"
            await _assert_columns(connection)
            await _assert_constraints(connection)
        await _exercise_rows(engine)
    finally:
        await engine.dispose()


async def _assert_columns(connection: object) -> None:
    from sqlalchemy.ext.asyncio import AsyncConnection

    assert isinstance(connection, AsyncConnection)
    for table_name, columns in EXPECTED_COLUMNS.items():
        rows = (
            await connection.execute(
                text(
                    "SELECT column_name, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = :table_name"
                ),
                {"table_name": table_name},
            )
        ).all()
        found = {str(name): nullable == "YES" for name, nullable in rows}
        assert set(found) == columns
        model_columns = Base.metadata.tables[table_name].columns
        for name, nullable in found.items():
            assert model_columns[name].nullable is nullable


async def _assert_constraints(connection: object) -> None:
    from sqlalchemy.ext.asyncio import AsyncConnection

    assert isinstance(connection, AsyncConnection)
    rows = (
        await connection.execute(
            text(
                "SELECT rel.relname, con.conname "
                "FROM pg_constraint AS con "
                "JOIN pg_class AS rel ON rel.oid = con.conrelid "
                "JOIN pg_namespace AS namespace ON namespace.oid = rel.relnamespace "
                "WHERE namespace.nspname = 'public'"
            )
        )
    ).all()
    by_table: dict[str, set[str]] = {}
    for table_name, constraint_name in rows:
        by_table.setdefault(str(table_name), set()).add(str(constraint_name))
    for table_name, names in EXPECTED_CONSTRAINTS.items():
        assert names <= by_table[table_name]


async def _exercise_rows(engine: AsyncEngine) -> None:
    suffix = uuid4().hex
    email = f"visitor-{suffix}@example.com"
    async with engine.begin() as connection:
        user_id = await connection.scalar(
            text(
                "INSERT INTO users (email, password_hash, full_name, role) "
                "VALUES (:email, 'hash', 'Visitor', 'member') "
                "RETURNING id"
            ),
            {"email": email},
        )
        await connection.execute(
            text(
                "INSERT INTO auth_sessions (token_hash, user_id, expires_at, user_agent) "
                "VALUES (:token_hash, :user_id, :expires_at, 'pytest')"
            ),
            {
                "token_hash": f"token-{suffix}",
                "user_id": user_id,
                "expires_at": datetime.now(UTC),
            },
        )
        await connection.execute(
            text(
                "INSERT INTO rate_limit_windows (bucket_key, window_start, count) "
                "VALUES (:bucket_key, :window_start, 1)"
            ),
            {"bucket_key": f"bucket-{suffix}", "window_start": datetime.now(UTC)},
        )
        await connection.execute(
            text(
                "INSERT INTO audit_events (actor_user_id, action, target_type, target_id) "
                "VALUES (:user_id, 'account.delete', 'user', :user_id)"
            ),
            {"user_id": user_id},
        )
    async with engine.connect() as connection:
        with pytest.raises(IntegrityError):
            async with connection.begin():
                await connection.execute(
                    text(
                        "INSERT INTO users (email, password_hash, full_name, role) "
                        "VALUES ('Visitor@Example.com', 'hash', 'Visitor', 'member')"
                    )
                )
        with pytest.raises(IntegrityError):
            async with connection.begin():
                await connection.execute(
                    text(
                        "INSERT INTO users (email, password_hash, full_name, role) "
                        "VALUES (:email, 'hash', 'Other', 'member')"
                    ),
                    {"email": email},
                )
        with pytest.raises(IntegrityError):
            async with connection.begin():
                await connection.execute(
                    text(
                        "INSERT INTO users (email, password_hash, full_name, role) "
                        "VALUES ('other@example.com', 'hash', 'Other', 'owner')"
                    )
                )
        with pytest.raises(IntegrityError):
            async with connection.begin():
                await connection.execute(
                    text(
                        "INSERT INTO users "
                        "(email, password_hash, full_name, role, visitor_type) "
                        "VALUES ('typed@example.com', 'hash', 'Other', 'member', 'doctor')"
                    )
                )


async def _set_vector_extension(database_url: str, *, present: bool) -> None:
    engine = create_async_engine(database_url)
    statement = (
        "CREATE EXTENSION IF NOT EXISTS vector" if present else "DROP EXTENSION IF EXISTS vector"
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(text(statement))
    finally:
        await engine.dispose()
