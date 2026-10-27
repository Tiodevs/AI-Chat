"""Abre uma sessão assíncrona e a fecha no fim do uso. Seção 6.2 do SDD."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import pool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

CONNECT_TIMEOUT_SECONDS = 10


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


def make_engine(database_url: str) -> AsyncEngine:
    url, connect_args = adapt_asyncpg_url(database_url)
    connect_args["timeout"] = CONNECT_TIMEOUT_SECONDS
    return create_async_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )


@asynccontextmanager
async def open_session(database_url: str) -> AsyncIterator[AsyncSession]:
    """Uma conexão por uso. A prontidão não segura pool entre pedidos."""
    engine = make_engine(database_url)
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()
