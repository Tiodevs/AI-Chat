"""Concede e revoga o papel `attendant`. Seção 29.3 do SDD.

Uso, em `apps/api`:

- `python -m app.scripts.attendants grant EMAIL --by EMAIL_DO_ADMIN`: promove a conta
  `member`, criada pela própria pessoa no formulário, e revoga as sessões dela, para a próxima
  entrada já nascer com a sessão de 12 horas da equipe.
- `python -m app.scripts.attendants revoke EMAIL --by EMAIL_DO_ADMIN`: volta a conta para
  `member`, devolve os atendimentos dela à fila, apaga a presença e revoga as sessões.

Na Railway, roda com `railway run`. As duas operações gravam `attendant.grant` ou
`attendant.revoke`, com o admin de `--by` como ator. O script recusa mudar um admin. Um erro
de domínio sai com código 1 e a mensagem.
"""

import argparse
import asyncio
import sys

from app.adapters.clock import SystemClock
from app.core.config import Settings
from app.domain.errors import DomainError
from app.prompts.auth import DATABASE_URL_MISSING
from app.services.attendant_roles import AttendantRoleService


def main(argv: list[str] | None = None) -> None:
    """Lê a ação, o e-mail e o `--by`, confere o banco e roda o caso de uso."""
    parser = argparse.ArgumentParser(description="Concede ou revoga o papel attendant.")
    parser.add_argument("action", choices=["grant", "revoke"])
    parser.add_argument("email")
    parser.add_argument("--by", required=True, metavar="EMAIL_DO_ADMIN")
    args = parser.parse_args(argv)
    settings = Settings()
    if not settings.database_url:
        print(DATABASE_URL_MISSING, file=sys.stderr)
        raise SystemExit(1)
    service = AttendantRoleService(database_url=settings.database_url, clock=SystemClock())
    try:
        if args.action == "grant":
            change = asyncio.run(service.grant(args.email, by=args.by))
            print(f"Papel attendant concedido. Sessões revogadas: {change.sessions_revoked}.")
        else:
            change = asyncio.run(service.revoke(args.email, by=args.by))
            print(
                "Papel attendant revogado. "
                f"Sessões revogadas: {change.sessions_revoked}. "
                f"Atendimentos devolvidos à fila: {change.handoffs_released}."
            )
    except DomainError as exc:
        print(exc.message, file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
