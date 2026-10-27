"""Cria o primeiro admin ou remove um, com lock. Seção 10.5 do SDD."""

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
