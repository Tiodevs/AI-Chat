"""Fixtures do banco da integração: só PostgreSQL local, migrado uma vez. Seção 21.1 do SDD.

`database_url` lê `DATABASE_URL` e aceita só `localhost`, `127.0.0.1` ou `::1`, para nenhum
teste tocar um banco da Railway. Sem banco local, a suíte pula; com `REQUIRE_INTEGRATION_DB=1`,
como no job `api` do `ci.yml`, ela falha (NFR-5). `migrated_database` roda as migrações do
Alembic uma vez por sessão do pytest e devolve a URL. Os testes dividem esse banco sem rollback
automático: cada arquivo usa ids, e-mails e IPs únicos e faz a própria limpeza.
`test_database.py` testa as duas funções de URL sem banco.
"""

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
    """Só um banco local entra na suíte. A CI usa 127.0.0.1.

    Devolve a URL com o esquema `postgresql+asyncpg://`, ou `None` para uma URL vazia ou de
    outro host, como a da Railway.
    """
    candidate = raw.strip()
    if not candidate:
        return None
    host = urlparse(candidate).hostname
    if host not in _LOCAL_HOSTS:
        return None
    return rewrite_database_url(candidate)


def resolve_integration_database(raw_url: str, required: str) -> str:
    """Sem banco local, a suíte pula. Com `REQUIRE_INTEGRATION_DB=1`, como na CI, ela falha.

    Assim a CI não fica verde com a integração inteira pulada. Seção 21.1 do SDD. Com banco
    local, devolve a URL de `integration_database_url`.
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
    """URL do banco local, lida de `DATABASE_URL` uma vez por sessão do pytest.

    Sem banco local, a suíte pula; com `REQUIRE_INTEGRATION_DB=1`, ela falha.
    """
    return resolve_integration_database(
        os.environ.get("DATABASE_URL", ""),
        os.environ.get(REQUIRE_DATABASE_ENV, ""),
    )


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> Iterator[str]:
    """Banco migrado até `head` uma vez por sessão do pytest. Devolve a mesma URL.

    Roda o `upgrade head` duas vezes: a segunda encontra o banco no topo e não muda nada, como
    no pré-deploy de cada deploy (seção 22.1). O `%` vira `%%` porque o `Config` do Alembic
    interpola a URL como o `configparser`. Não há limpeza no fim: os testes dividem este banco.
    """
    from alembic import command
    from alembic.config import Config

    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    yield database_url
