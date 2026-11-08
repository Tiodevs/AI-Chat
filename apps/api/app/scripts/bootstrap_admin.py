"""Cria o primeiro admin ou remove um, com lock. Seção 10.5 do SDD.

Uso, em `apps/api`:

- `python -m app.scripts.bootstrap_admin`: se nenhum usuário tem `role = admin`, cria um com
  `ADMIN_EMAIL` e `ADMIN_PASSWORD`. Se já existe um admin, as duas variáveis são ignoradas.
- `python -m app.scripts.bootstrap_admin --remove EMAIL`: remove o admin com esse e-mail e
  as sessões dele, e recusa remover o último admin. Na Railway, roda com `railway run`.

Roda no pré-deploy da Railway, antes da semente, que precisa de um admin como autor dos
documentos (seção 22.1). O `BootstrapAdminService` pega um `pg_advisory_lock`, então duas
execuções simultâneas não criam dois admins (seção 6.4). Precisa de `DATABASE_URL`. Um erro de
domínio, como credenciais vazias ou inválidas, sai com código 1 e a mensagem.
"""

import argparse
import asyncio
import sys

from app.adapters.clock import SystemClock
from app.adapters.password_hasher import get_password_hasher
from app.core.config import Settings
from app.domain.errors import DomainError
from app.prompts.auth import ADMIN_CREATED, ADMIN_EXISTS, ADMIN_REMOVED, DATABASE_URL_MISSING
from app.services.auth import BootstrapAdminService


def main(argv: list[str] | None = None) -> None:
    """Lê `--remove`, confere o banco e roda o caso de uso. Sem `argv`, lê `sys.argv`."""
    parser = argparse.ArgumentParser(description="Cria ou remove o admin inicial.")
    parser.add_argument("--remove", metavar="EMAIL", help="Remove o admin com este e-mail.")
    args = parser.parse_args(argv)
    settings = Settings()
    if not settings.database_url:
        print(DATABASE_URL_MISSING, file=sys.stderr)
        raise SystemExit(1)
    try:
        asyncio.run(_run(settings, args.remove))
    except DomainError as exc:
        print(exc.message, file=sys.stderr)
        raise SystemExit(1) from exc


async def _run(settings: Settings, remove: str | None) -> None:
    """Remove o admin pedido ou garante o primeiro, e imprime o que aconteceu."""
    service = BootstrapAdminService(
        database_url=settings.database_url,
        clock=SystemClock(),
        hasher=get_password_hasher(),
    )
    if remove is not None:
        await service.remove(remove)
        print(ADMIN_REMOVED)
        return
    created = await service.ensure(email=settings.admin_email, password=settings.admin_password)
    print(ADMIN_CREATED if created else ADMIN_EXISTS)


if __name__ == "__main__":
    main()
