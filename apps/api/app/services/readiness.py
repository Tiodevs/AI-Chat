"""Prontidão do banco. A conferência de dimensão entra com a tabela chunks. NFR-9."""

import structlog

from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.repositories.readiness import ReadinessRepository


class ReadinessService:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def is_ready(self) -> bool:
        if not self._database_url:
            _log_failure("database_unconfigured")
            return False
        try:
            async with open_session(self._database_url) as session, UnitOfWork(session):
                repository = ReadinessRepository(session)
                await repository.ping()
                if not await repository.vector_extension_installed():
                    _log_failure("vector_missing")
                    return False
        except Exception:
            _log_failure("database_unreachable")
            return False
        return True


def _log_failure(reason: str) -> None:
    structlog.get_logger("atrium").warning("readiness.failed", reason=reason)
