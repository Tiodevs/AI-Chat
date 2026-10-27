import os
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import pytest

from app.core.config import rewrite_database_url

API_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def integration_database_url(raw: str) -> str | None:
    """Só um banco local entra na suíte. A CI usa 127.0.0.1."""
    candidate = raw.strip()
    if not candidate:
        return None
    host = urlparse(candidate).hostname
    if host not in _LOCAL_HOSTS:
        return None
    return rewrite_database_url(candidate)


@pytest.fixture(scope="session")
def database_url() -> str:
    url = integration_database_url(os.environ.get("DATABASE_URL", ""))
    if url is None:
        pytest.skip(
            "Integration tests need DATABASE_URL on localhost. "
            "CI provides pgvector; a remote URL is ignored."
        )
    return url


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> Iterator[str]:
    from alembic import command
    from alembic.config import Config

    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    yield database_url
