"""Consultas de users. Seção 8.1 do SDD.

Camada de repositório (seção 6.2 do SDD). Lê e grava `users`. Quem usa: o `AuthService`
(login e a sessão de cada pedido), o `RegistrationService` (e-mail já usado e o membro novo),
o `AccountService` (perfil, consentimento de personalização e exclusão) e o
`BootstrapAdminService` (admin inicial e remoção). Devolve a entidade `User`; a sessão é
criada com `expire_on_commit=False`, então os atributos continuam legíveis depois do commit.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Consultas da tabela de contas."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        """Conta com este e-mail, ou `None`. Usa o índice único `users_email_key`.

        O e-mail precisa chegar normalizado em minúsculas: o banco só guarda assim, e a
        comparação é exata.
        """
        return await self._session.scalar(select(User).where(User.email == email))

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Conta pela chave primária, ou `None`.

        `AsyncSession.get` olha primeiro o mapa de identidade da sessão e só consulta o banco
        se a entidade ainda não foi carregada.
        """
        return await self._session.get(User, user_id)

    async def touch(self, user_id: UUID, now: datetime) -> None:
        """Marca a entrada: grava `last_seen_at`, que a retenção de contas inativas usa.

        Só o login chama. Um pedido com sessão já aberta não atualiza a coluna.
        """
        await self._session.execute(
            update(User).where(User.id == user_id).values(last_seen_at=now, updated_at=now)
        )

    async def update_profile(
        self,
        user_id: UUID,
        values: dict[str, str | None],
        now: datetime,
    ) -> None:
        """Grava só as colunas de `values`, mais `updated_at`. Sem valores, não faz nada.

        As chaves vêm do plano do domínio (`plan_profile_update`), nunca do corpo do pedido
        direto. A revogação da personalização usa o mesmo método para limpar `visitor_type` e
        `visit_reason`.
        """
        if not values:
            return
        await self._session.execute(
            update(User).where(User.id == user_id).values(**values, updated_at=now)
        )

    async def count_by_role(self, role: str) -> int:
        """Quantas contas têm o papel. O bootstrap conta os admins sob o advisory lock."""
        value = await self._session.scalar(
            select(func.count()).select_from(User).where(User.role == role)
        )
        return int(value or 0)

    async def insert(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: str,
        role: str,
        now: datetime,
        phone: str | None = None,
        visitor_type: str | None = None,
        visit_reason: str | None = None,
    ) -> UUID:
        """Cria a conta com id gerado no Python e as três datas iguais a `now`. Devolve o id.

        Um e-mail repetido viola `users_email_key` no `flush()`, com `IntegrityError`; o
        cadastro transforma esse erro em 409.
        """
        user_id = uuid4()
        self._session.add(
            User(
                id=user_id,
                email=email,
                password_hash=password_hash,
                full_name=full_name,
                role=role,
                phone=phone,
                visitor_type=visitor_type,
                visit_reason=visit_reason,
                last_seen_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        await self._session.flush()
        return user_id

    async def delete_user(self, user_id: UUID) -> None:
        """Apaga a conta. As tabelas filhas com cascata vão junto (veja `User`).

        As sessões de autenticação precisam sair antes, porque a chave estrangeira delas não
        tem cascata. Um admin com documentos também não sai: `documents.created_by` não tem
        cascata.
        """
        await self._session.execute(delete(User).where(User.id == user_id))
