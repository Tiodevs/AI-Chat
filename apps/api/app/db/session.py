"""Sessões assíncronas: pool por processo na API, uma conexão por uso fora dela. Seção 6.4.

Camada de persistência. Os serviços abrem toda sessão com `open_session`, quase sempre junto
com a unidade de trabalho:

    async with open_session(url) as session, UnitOfWork(session):
        ...

O `async with` com dois gerenciadores abre na ordem e fecha ao contrário: primeiro a
`UnitOfWork` faz commit ou rollback, depois a sessão fecha. O `lifespan` de `app/main.py`
chama `start_pool` na subida e `close_pool` no fim. O `alembic/env.py` e a semente usam
`make_engine` direto. O driver é o asyncpg, pela URL `postgresql+asyncpg://` que
`app.core.config` monta.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import pool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Prazo, em segundos, para o asyncpg abrir uma conexão, com ou sem pool.
CONNECT_TIMEOUT_SECONDS = 10
# Números da seção 6.4: 5 conexões, mais 5 de folga, até 10 s de espera por uma conexão livre
# e reciclagem a cada 30 minutos (1.800 s).
POOL_SIZE = 5
POOL_MAX_OVERFLOW = 5
POOL_TIMEOUT_SECONDS = 10
POOL_RECYCLE_SECONDS = 1800


@dataclass(frozen=True, slots=True)
class _Pool:
    """O engine com pool e a fábrica das sessões dele."""

    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


# Um pool por URL e por loop de eventos. O asyncpg prende cada conexão ao loop que a abriu,
# então um loop diferente, como o `asyncio.run` de um teste, segue com uma conexão por uso.
_pools: dict[tuple[str, asyncio.AbstractEventLoop], _Pool] = {}


def adapt_asyncpg_url(database_url: str) -> tuple[str, dict[str, object]]:
    """Tira sslmode da query. O asyncpg recebe o mesmo valor em ssl.

    `sslmode` é o nome do libpq, e o asyncpg, chamado pelo SQLAlchemy, não o aceita. Devolve
    a URL sem ele e os `connect_args` com `ssl`. Um `sslmode` repetido vale o primeiro.
    `render_as_string(hide_password=False)` mantém a senha, que o `str()` da URL esconderia.
    """
    url = make_url(database_url)
    sslmode = url.query.get("sslmode")
    connect_args: dict[str, object] = {}
    if isinstance(sslmode, tuple):
        sslmode = sslmode[0] if sslmode else None
    if isinstance(sslmode, str) and sslmode:
        connect_args["ssl"] = sslmode
        url = url.difference_update_query(["sslmode"])
    return url.render_as_string(hide_password=False), connect_args


def make_engine(database_url: str, *, pooled: bool = False) -> AsyncEngine:
    """Cria o engine assíncrono. Não conecta: a primeira conexão abre no primeiro uso.

    Sem `pooled`, usa `NullPool`: cada sessão abre a própria conexão e a fecha ao devolver.
    Com `pooled`, usa o pool da seção 6.4, e `pool_pre_ping` testa a conexão antes de
    entregá-la, trocando uma que o banco já fechou.
    """
    url, connect_args = adapt_asyncpg_url(database_url)
    connect_args["timeout"] = CONNECT_TIMEOUT_SECONDS
    if not pooled:
        return create_async_engine(
            url,
            poolclass=pool.NullPool,
            connect_args=connect_args,
        )
    return create_async_engine(
        url,
        connect_args=connect_args,
        pool_size=POOL_SIZE,
        max_overflow=POOL_MAX_OVERFLOW,
        pool_timeout=POOL_TIMEOUT_SECONDS,
        pool_recycle=POOL_RECYCLE_SECONDS,
        pool_pre_ping=True,
    )


async def start_pool(database_url: str) -> AsyncEngine:
    """Abre o pool do processo da API no loop atual. O `lifespan` chama no início.

    Um pool anterior da mesma URL no mesmo loop é fechado antes. `expire_on_commit=False`
    deixa os objetos lidos usáveis depois do commit: numa sessão assíncrona, recarregar um
    atributo vencido pediria uma ida ao banco que o SQLAlchemy não faz por conta própria.
    """
    key = (database_url, asyncio.get_running_loop())
    previous = _pools.pop(key, None)
    if previous is not None:
        await previous.engine.dispose()
    engine = make_engine(database_url, pooled=True)
    _pools[key] = _Pool(engine, async_sessionmaker(engine, expire_on_commit=False))
    return engine


async def close_pool(database_url: str) -> None:
    """Fecha o pool do loop atual. O `lifespan` chama no fim. Sem pool aberto, não faz nada."""
    closed = _pools.pop((database_url, asyncio.get_running_loop()), None)
    if closed is not None:
        await closed.engine.dispose()


def pooled_engines(database_url: str) -> list[AsyncEngine]:
    """Os engines com pool abertos para a URL, em qualquer loop. Serve aos testes."""
    return [entry.engine for (url, _loop), entry in _pools.items() if url == database_url]


@asynccontextmanager
async def open_session(database_url: str, *, fresh: bool = False) -> AsyncIterator[AsyncSession]:
    """Sessão do pool quando a API o abriu neste loop. Sem pool, uma conexão por uso.

    Scripts, o `retention-job` e os testes sem `lifespan` seguem com uma conexão por uso.
    `fresh` força a conexão própria, como no `/ready`, que confere se o banco aceita conexão.

    A sessão fecha na saída do `async with`, mesmo com exceção, e devolve a conexão ao pool;
    sem pool, o engine de uso único também é descartado. A transação fica com a `UnitOfWork`.
    Uma URL vazia ou inválida levanta erro do SQLAlchemy ao criar o engine.
    """
    # O pool é por loop: o `asyncio.run` de um script ou de um teste não acha o da API.
    shared = None if fresh else _pools.get((database_url, asyncio.get_running_loop()))
    if shared is not None:
        pooled = shared.sessions()
        try:
            yield pooled
        finally:
            await pooled.close()
        return
    engine = make_engine(database_url)
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()
