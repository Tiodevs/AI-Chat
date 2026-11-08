"""Tarefa agendada `retention-job`. Seções 11.6 e 22.1 do SDD.

Uso: `python -m app.scripts.retention`.

Na Railway, o serviço `retention-job` roda este comando todo dia às 06:00 UTC
(`0 6 * * *`), sem nova tentativa. O `RetentionService` aplica as regras da seção 11.6, cada
uma na própria transação, e grava uma linha por regra em `retention_runs`, que alimenta as
métricas `atrium_retention_*` da API (seção 18.3). Apaga dados de verdade: rode à mão só contra
um banco de desenvolvimento.

Precisa só de `DATABASE_URL`. Não passa pela conferência de subida da API (`require_safeguards`),
porque o job não usa o teto de tokens, as chaves de HMAC nem o segredo da borda (seção 7.1).
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
    """Roda todas as regras e imprime `regra: apagados` de cada uma e a linha final.

    Uma regra que falha interrompe as seguintes e sai com erro; as anteriores já foram
    confirmadas.
    """
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
