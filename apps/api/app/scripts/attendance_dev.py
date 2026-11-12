"""Ferramentas do atendimento humano para a máquina local. Seção 29 do SDD, Etapa 17.4.

Uso, em `apps/api` ou no contêiner `api` do `docker-compose.yml`:

- `python -m app.scripts.attendance_dev seed`: cria, ou deixa como novas, as duas contas de
  teste do atendimento: a atendente `ATTENDANT_EMAIL` e a visitante `VISITOR_EMAIL`, com as
  senhas abaixo, os aceites dos Termos e a maioridade. A atendente recebe o papel pelo mesmo
  caso de uso do script `attendants`, com o primeiro admin do banco como ator.
- `python -m app.scripts.attendance_dev present EMAIL`: mantém a pessoa da equipe presente por
  10 minutos, com um sinal a cada 15 segundos, para testar o pedido antes do console.

Só roda com `APP_ENV` `local` ou `test`: as senhas são fixas e públicas, como a do admin
local do `docker-compose.yml`. Nunca use estas contas fora da máquina local.
"""

import argparse
import asyncio
import sys
from uuid import UUID

from app.adapters.clock import SystemClock
from app.adapters.password_hasher import get_password_hasher
from app.core.config import Settings
from app.db.session import open_session
from app.db.unit_of_work import UnitOfWork
from app.domain.errors import DomainError
from app.domain.handoff import PresenceStatus
from app.domain.legal import LEGAL_DOCUMENT_VERSION
from app.domain.registration import ConsentGrant
from app.prompts.auth import DATABASE_URL_MISSING
from app.repositories.consents import ConsentRepository
from app.repositories.handoffs import HandoffRepository
from app.repositories.users import UserRepository
from app.services.attendant_roles import AttendantRoleService

# As contas de teste do atendimento, só para a máquina local.
ATTENDANT_EMAIL = "atendente@example.com"
ATTENDANT_PASSWORD = "Atrium-local-2026-atendente"
ATTENDANT_NAME = "Rita Atendente"
VISITOR_EMAIL = "visitante@example.com"
VISITOR_PASSWORD = "Atrium-local-2026-visitante"
VISITOR_NAME = "Ana Visitante"
# Quanto tempo `present` mantém a presença e de quanto em quanto tempo manda o sinal.
_PRESENT_SECONDS = 600
_SIGNAL_SECONDS = 15
_LOCAL_ENVIRONMENTS = frozenset({"local", "test"})


def main(argv: list[str] | None = None) -> None:
    """Lê o comando e roda `seed` ou `present`. Fora de `local` e `test`, sai com 1."""
    parser = argparse.ArgumentParser(description="Atendimento humano na máquina local.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed", help="Cria as contas de teste do atendimento.")
    present = commands.add_parser("present", help="Mantém uma pessoa da equipe presente.")
    present.add_argument("email")
    args = parser.parse_args(argv)
    settings = Settings()
    if settings.app_env not in _LOCAL_ENVIRONMENTS:
        print("Este script só roda com APP_ENV local ou test.", file=sys.stderr)
        raise SystemExit(1)
    if not settings.database_url:
        print(DATABASE_URL_MISSING, file=sys.stderr)
        raise SystemExit(1)
    try:
        if args.command == "seed":
            asyncio.run(seed(settings.database_url))
            print(f"Contas de teste prontas: {ATTENDANT_EMAIL} e {VISITOR_EMAIL}.")
        else:
            asyncio.run(_present(settings.database_url, args.email))
    except DomainError as exc:
        print(exc.message, file=sys.stderr)
        raise SystemExit(1) from exc


async def seed(database_url: str) -> None:
    """Cria as duas contas, ou troca a senha delas pela de teste, e concede o papel.

    1. A visitante e a atendente nascem como `member`, com o aceite dos Termos na versão
       vigente e a maioridade, como no formulário.
    2. A atendente vira `attendant` pelo `AttendantRoleService`, com o primeiro admin como
       ator de `attendant.grant`. Uma atendente que já tem o papel fica como está.
    """
    clock = SystemClock()
    hasher = get_password_hasher()
    admin_email: str | None = None
    attendant_role = "member"
    # 1.
    for email, password, name in (
        (VISITOR_EMAIL, VISITOR_PASSWORD, VISITOR_NAME),
        (ATTENDANT_EMAIL, ATTENDANT_PASSWORD, ATTENDANT_NAME),
    ):
        now = clock.now()
        async with open_session(database_url) as session, UnitOfWork(session):
            users = UserRepository(session)
            user = await users.get_by_email(email)
            if user is None:
                user_id: UUID = await users.insert(
                    email=email,
                    password_hash=hasher.hash_password(password),
                    full_name=name,
                    role="member",
                    now=now,
                )
                await ConsentRepository(session).insert_grants(
                    user_id=user_id,
                    grants=(
                        ConsentGrant("terms_and_privacy_notice", LEGAL_DOCUMENT_VERSION),
                        ConsentGrant("age_18_plus", LEGAL_DOCUMENT_VERSION),
                    ),
                    source="form",
                    granted_at=now,
                )
            else:
                await users.set_password_hash(user.id, hasher.hash_password(password), now)
                if email == ATTENDANT_EMAIL:
                    attendant_role = user.role
            admin_email = await users.first_email_with_role("admin") or admin_email
    # 2.
    if attendant_role == "member":
        if admin_email is None:
            print("Nenhum admin no banco: rode antes o bootstrap_admin.", file=sys.stderr)
            raise SystemExit(1)
        await AttendantRoleService(database_url=database_url, clock=clock).grant(
            ATTENDANT_EMAIL, by=admin_email
        )


async def _present(database_url: str, email: str) -> None:
    """Marca a pessoa como `available` e manda o sinal a cada 15 segundos, por 10 minutos."""
    clock = SystemClock()
    async with open_session(database_url) as session, UnitOfWork(session):
        user = await UserRepository(session).get_by_email(email.strip().lower())
        if user is None or user.role not in ("attendant", "admin"):
            print("O e-mail precisa ser de uma pessoa da equipe.", file=sys.stderr)
            raise SystemExit(1)
        user_id = user.id
    print(f"Presente por {_PRESENT_SECONDS // 60} minutos. Ctrl+C encerra.")
    for _ in range(_PRESENT_SECONDS // _SIGNAL_SECONDS):
        async with open_session(database_url) as session, UnitOfWork(session):
            await HandoffRepository(session).set_presence(
                user_id, PresenceStatus.AVAILABLE.value, clock.now()
            )
        await asyncio.sleep(_SIGNAL_SECONDS)


if __name__ == "__main__":
    main()
