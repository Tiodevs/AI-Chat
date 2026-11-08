"""Transação curta. Avisa no log quando passa de 2 segundos. Seção 6.4 do SDD.

Camada de persistência: o padrão Unit of Work da seção 6.2. O serviço é o dono da transação
e a abre com `async with UnitOfWork(session):`. Os repositórios recebem a mesma sessão e não
fazem commit; a exceção é o `SeedLock` da semente, numa conexão própria. Nenhuma chamada ao
Gemini ou ao LangSmith acontece com a transação aberta (seção 6.4).
"""

from __future__ import annotations

import time
from types import TracebackType

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

# Seção 6.4: o aviso sai acima de 2 s, não em 2 s exatos.
SLOW_TRANSACTION_SECONDS = 2.0


class UnitOfWork:
    """Abre uma transação na entrada do `async with` e a encerra na saída.

    Sem exceção no bloco, faz commit; com qualquer exceção, inclusive o cancelamento, faz
    rollback e deixa a exceção subir. Nos dois casos, mede o tempo, avisa com
    `unit_of_work.slow` acima de 2 s e fecha a sessão. Um erro do próprio commit, como uma
    restrição violada, também sobe depois do fechamento.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._started = 0.0

    async def __aenter__(self) -> UnitOfWork:
        """Começa a transação. Se o `begin` falhar, fecha a sessão antes de subir o erro."""
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
        """Commit ou rollback, aviso de lentidão e fechamento da sessão.

        Devolve `False`: o `async with` não engole a exceção do bloco.
        """
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
        """Registra `unit_of_work.slow` com `duration_ms` se a transação passou do limite."""
        elapsed = time.perf_counter() - self._started
        if elapsed > SLOW_TRANSACTION_SECONDS:
            structlog.get_logger("atrium").warning(
                "unit_of_work.slow",
                duration_ms=int(elapsed * 1000),
            )
