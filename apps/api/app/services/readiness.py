"""Prontidão do banco: conexão, extensão `vector` e dimensão do embedding. NFR-9.

Camada de serviço. `controllers/readiness.py` chama `ReadinessService.is_ready` em
`GET /ready` (seção 12), que é o health check do serviço da API na Railway (seção 22.1) e
um dos pontos da fumaça do deploy (seção 22.3). Usa `ReadinessRepository`. A dimensão
esperada vem de `EMBEDDING_DIMENSIONS`, e a seção 8.3 explica por que ela precisa bater com
o tipo da coluna `chunks.embedding`.
"""

import structlog

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.repositories.readiness import ReadinessRepository


class ReadinessService:
    """Confere se a API pode atender pedidos que usam o banco."""

    def __init__(self, database_url: str, embedding_dimensions: int = 768) -> None:
        self._database_url = database_url
        self._embedding_dimensions = embedding_dimensions

    async def is_ready(self) -> bool:
        """Verdadeiro quando o banco responde, `vector` existe e a coluna é `vector(N)`.

        Nunca levanta: cada falha vira `False` e o log `readiness.failed` com o motivo
        (`database_unconfigured`, `vector_missing`, `dimension_mismatch` ou
        `database_unreachable`), sem texto de erro. Usa uma transação curta de leitura numa
        conexão nova, fora do pool.
        """
        if not self._database_url:
            _log_failure("database_unconfigured")
            return False
        try:
            # Conexão própria: o pool reaproveitaria uma conexão e esconderia um banco que
            # parou de aceitar conexões novas.
            async with (
                open_session(self._database_url, fresh=True) as session,
                UnitOfWork(session),
            ):
                repository = ReadinessRepository(session)
                await repository.ping()
                if not await repository.vector_extension_installed():
                    _log_failure("vector_missing")
                    return False
                column_type = await repository.embedding_column_type()
                expected = f"vector({self._embedding_dimensions})"
                # Mudar a dimensão exige migração e re-embedding completo (seção 8.3).
                if column_type != expected:
                    _log_failure("dimension_mismatch")
                    return False
        except Exception:
            _log_failure("database_unreachable")
            return False
        return True


def _log_failure(reason: str) -> None:
    """Log de aviso com um motivo fixo, para o operador saber qual conferência falhou."""
    structlog.get_logger("atrium").warning("readiness.failed", reason=reason)
