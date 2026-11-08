"""Lock do admin inicial. Duas execuções simultâneas não duplicam. Seção 6.4.

Camada de repositório (seção 6.2 do SDD). `BootstrapAdminService.ensure` e `remove`, chamados
por `python -m app.scripts.bootstrap_admin` no pré-deploy, pegam este lock antes de contar e
gravar admins. Seção 10.5 do SDD.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Número do advisory lock. O valor não significa nada: basta ser o mesmo em toda execução e
# diferente de `SEED_LOCK_KEY`, para o lock da semente e este não se bloquearem.
BOOTSTRAP_LOCK_KEY = 22022026


class BootstrapRepository:
    """Serializa as execuções do bootstrap do admin com um advisory lock do PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def lock(self) -> None:
        """Pega o lock do admin inicial, esperando se outra execução já o tem.

        Um advisory lock é um lock do PostgreSQL sobre um número escolhido pela aplicação, e
        não sobre uma linha. A variante `pg_advisory_xact_lock` dura até o fim da transação: o
        commit ou o rollback da `UnitOfWork` o solta sozinho. Com ele, contar os admins e criar
        o primeiro acontecem sem outra execução no meio, e duas execuções simultâneas criam um
        admin só. A seção 6.4 cita `pg_advisory_lock`; aqui é a variante de transação, e a
        semente usa a de sessão (`SeedLock`).
        """
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": BOOTSTRAP_LOCK_KEY},
        )
