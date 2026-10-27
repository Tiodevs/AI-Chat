"""Lock do admin inicial. Duas execuções simultâneas não duplicam. Seção 6.4."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

BOOTSTRAP_LOCK_KEY = 22022026


class BootstrapRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock(self) -> None:
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": BOOTSTRAP_LOCK_KEY},
        )
