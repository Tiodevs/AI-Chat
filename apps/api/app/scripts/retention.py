"""Tarefa agendada `retention-job`. Seções 11.6 e 22.1 do SDD.

Uso: `python -m app.scripts.retention`.
"""

import asyncio
import sys

from app.adapters.clock import SystemClock
from app.core.config import Settings
from app.core.logging import configure_logging
from app.prompts.auth import DATABASE_URL_MISSING
from app.prompts.privacy import RETENTION_DONE
from app.services.retention import RetentionService


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    if not settings.database_url:
        print(DATABASE_URL_MISSING, file=sys.stderr)
        raise SystemExit(1)
    results = asyncio.run(
        RetentionService(database_url=settings.database_url, clock=SystemClock()).run_all()
    )
    for result in results:
        print(f"{result.rule.value}: {result.deleted_count}")
    print(RETENTION_DONE)


if __name__ == "__main__":
    main()
