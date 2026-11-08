"""Migrações assíncronas. A URL vem do Alembic ou de DATABASE_URL. Seção 8 do SDD.

O Alembic executa este arquivo nos comandos que falam com o banco, como `upgrade`,
`downgrade`, `current`, `stamp` e `revision --autogenerate`. Ele lê `alembic.ini`, liga o
logging do arquivo e roda as revisões de `versions/` no modo online, com conexão, ou no
offline (`--sql`), que só escreve o SQL.

O Alembic é síncrono, e a API usa o asyncpg. No modo online, `run_async_migrations` abre um
engine assíncrono sem pool (`app.db.session.make_engine`) e chama o código síncrono com
`connection.run_sync`. Com o PostgreSQL, o DDL é transacional: as revisões pendentes rodam numa
transação só, e uma falha no meio desfaz todas elas.

Quem roda: o pré-deploy da Railway (`alembic upgrade head`, seção 22.1), a pessoa no laptop e
a fixture `migrated_database` de `tests/integration/conftest.py`, que passa a URL do banco
local em `sqlalchemy.url`.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from app.core.config import Settings
from app.db.session import make_engine
from app.models import Base

# A configuração do Alembic: os valores do `alembic.ini` e os que um teste definiu por código.
config = context.config

# Liga o logging das seções `[loggers]`, `[handlers]` e `[formatters]` do `alembic.ini`.
# `disable_existing_loggers=False` mantém ligados os loggers criados antes.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Os modelos de `app.models`, que o `--autogenerate` compara com o banco.
target_metadata = Base.metadata


def database_url() -> str:
    """URL do banco das migrações.

    Vale o `sqlalchemy.url` da configuração, salvo o marcador `driver://` do `alembic.ini`.
    Sem ele, vale o `DATABASE_URL` do ambiente ou do `.env`, já reescrito para
    `postgresql+asyncpg://` pelo `Settings`. Uma URL dada em `sqlalchemy.url` não passa por
    essa reescrita e precisa já vir com o asyncpg. Levanta `RuntimeError` sem nenhuma das duas.
    """
    configured = config.get_main_option("sqlalchemy.url")
    if configured and not configured.startswith("driver://"):
        return configured
    settings = Settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL está vazio.")
    return settings.database_url


def run_migrations_offline() -> None:
    """Modo offline (`alembic upgrade head --sql`): escreve o SQL na saída, sem conectar.

    `literal_binds` põe os valores no próprio SQL, que não tem banco para receber parâmetros.
    """
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Roda as revisões pendentes numa transação, com a conexão síncrona do `run_sync`."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Abre o engine assíncrono sem pool, migra pela ponte `run_sync` e descarta o engine."""
    connectable = make_engine(database_url())
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Modo online: roda a versão assíncrona num loop de eventos novo (`asyncio.run`)."""
    asyncio.run(run_async_migrations())


# O Alembic escolhe o modo: a opção `--sql` liga o offline.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
