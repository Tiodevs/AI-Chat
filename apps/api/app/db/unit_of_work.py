"""Transação curta. Avisa no log quando passa de 2 segundos. Seção 6.4 do SDD."""

from __future__ import annotations

import time
from types import TracebackType

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

SLOW_TRANSACTION_SECONDS = 2.0


class UnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._started = 0.0

    async def __aenter__(self) -> UnitOfWork:
        self._started = time.perf_counter()
        try:
            await self.session.begin()
        except Exception:
            self._warn_if_slow()
            await self.session.close()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        try:
            if exc_type is None:
                await self.session.commit()
            else:
                await self.session.rollback()
        finally:
            self._warn_if_slow()
            await self.session.close()
        return False

    def _warn_if_slow(self) -> None:
        elapsed = time.perf_counter() - self._started
        if elapsed > SLOW_TRANSACTION_SECONDS:
            structlog.get_logger("atrium").warning(
                "unit_of_work.slow",
                duration_ms=int(elapsed * 1000),
            )
