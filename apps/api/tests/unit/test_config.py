from app.core.config import Settings, rewrite_database_url


def test_rewrites_postgresql_scheme_to_asyncpg() -> None:
    original = "postgresql://user:secret@localhost:5432/atrium"
    assert rewrite_database_url(original) == (
        "postgresql+asyncpg://user:secret@localhost:5432/atrium"
    )


def test_settings_rewrite_database_url() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://localhost:5432/atrium",
    )
    assert settings.database_url == "postgresql+asyncpg://localhost:5432/atrium"


def test_keeps_asyncpg_scheme() -> None:
    url = "postgresql+asyncpg://localhost:5432/atrium"
    assert rewrite_database_url(url) == url


def test_keeps_query_string() -> None:
    original = "postgresql://localhost:5432/atrium?sslmode=require"
    assert rewrite_database_url(original).endswith("?sslmode=require")
