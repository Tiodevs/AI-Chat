"""Consulta de prontidão: banco, extensão vector e dimensão. NFR-9."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ReadinessRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ping(self) -> None:
        await self._session.execute(text("SELECT 1"))

    async def vector_extension_installed(self) -> bool:
        result = await self._session.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        )
        return bool(result.scalar_one())

    async def embedding_column_type(self) -> str | None:
        result = await self._session.scalar(
            text(
                "SELECT format_type(attribute.atttypid, attribute.atttypmod) "
                "FROM pg_attribute AS attribute "
                "JOIN pg_class AS table_name ON table_name.oid = attribute.attrelid "
                "JOIN pg_namespace AS namespace ON namespace.oid = table_name.relnamespace "
                "WHERE namespace.nspname = 'public' "
                "AND table_name.relname = 'chunks' "
                "AND attribute.attname = 'embedding' "
                "AND NOT attribute.attisdropped"
            )
        )
        if result is None:
            return None
        return str(result)
