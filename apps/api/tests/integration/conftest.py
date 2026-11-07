import os
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import pytest

from app.core.config import rewrite_database_url

API_ROOT = Path(__file__).resolve().parents[2]
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
REQUIRE_DATABASE_ENV = "REQUIRE_INTEGRATION_DB"
_MISSING_DATABASE = (
    "Integration tests need DATABASE_URL on localhost. "
    "CI provides pgvector; a remote URL is ignored."
)


def integration_database_url(raw: str) -> str | None:
    """Só um banco local entra na suíte. A CI usa 127.0.0.1."""
    candidate = raw.strip()
    if not candidate:
        return None
    host = urlparse(candidate).hostname
    if host not in _LOCAL_HOSTS:
        return None
    return rewrite_database_url(candidate)


def resolve_integration_database(raw_url: str, required: str) -> str:
    """Sem banco local, a suíte pula. Com `REQUIRE_INTEGRATION_DB=1`, como na CI, ela falha.

    Assim a CI não fica verde com a integração inteira pulada. Seção 21.1 do SDD.
    """
    url = integration_database_url(raw_url)
    if url is not None:
        return url
    if required.strip() == "1":
        pytest.fail(
            f"{_MISSING_DATABASE} {REQUIRE_DATABASE_ENV}=1 turns the skip into a failure.",
            pytrace=False,
        )
    pytest.skip(_MISSING_DATABASE)


@pytest.fixture(scope="session")
def database_url() -> str:
    return resolve_integration_database(
        os.environ.get("DATABASE_URL", ""),
        os.environ.get(REQUIRE_DATABASE_ENV, ""),
    )


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> Iterator[str]:
    from alembic import command
    from alembic.config import Config

    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    yield database_url
