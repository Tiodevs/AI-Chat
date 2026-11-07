"""Sessões assíncronas: pool por processo na API, uma conexão por uso fora dela. Seção 6.4."""

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

CONNECT_TIMEOUT_SECONDS = 10
POOL_SIZE = 5
POOL_MAX_OVERFLOW = 5
POOL_TIMEOUT_SECONDS = 10
POOL_RECYCLE_SECONDS = 1800


@dataclass(frozen=True, slots=True)
class _Pool:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]


# Um pool por URL e por loop de eventos. O asyncpg prende cada conexão ao loop que a abriu,
# então um loop diferente, como o `asyncio.run` de um teste, segue com uma conexão por uso.
_pools: dict[tuple[str, asyncio.AbstractEventLoop], _Pool] = {}


def adapt_asyncpg_url(database_url: str) -> tuple[str, dict[str, object]]:
    """Tira sslmode da query. O asyncpg recebe o mesmo valor em ssl."""
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
    """Abre o pool do processo da API no loop atual. O `lifespan` chama no início."""
    key = (database_url, asyncio.get_running_loop())
    previous = _pools.pop(key, None)
    if previous is not None:
        await previous.engine.dispose()
    engine = make_engine(database_url, pooled=True)
    _pools[key] = _Pool(engine, async_sessionmaker(engine, expire_on_commit=False))
    return engine


async def close_pool(database_url: str) -> None:
    """Fecha o pool do loop atual. O `lifespan` chama no fim."""
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
    """
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
