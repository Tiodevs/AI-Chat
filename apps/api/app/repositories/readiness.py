"""Consulta de prontidão: o banco responde e a extensão vector existe. NFR-9."""

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
