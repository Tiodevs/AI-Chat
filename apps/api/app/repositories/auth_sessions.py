"""Sessões de autenticação. O banco guarda o SHA-256 do segredo. Seção 8.1.

Camada de repositório (seção 6.2 do SDD). Lê e grava `auth_sessions`. Quem usa: o `AuthService`
(login, logout e a sessão de cada pedido), o `RegistrationService` (a sessão aberta ao concluir
o cadastro), o `ConversationService` (quem é o membro do pedido) e, para apagar as sessões
antes do usuário, o `AccountService` e o `BootstrapAdminService`. Seção 10.3 do SDD.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_session import AuthSession


class AuthSessionRepository:
    """Cria, encontra, revoga e apaga sessões pelo hash do segredo do cookie."""

    def __init__(self, session: AsyncSession) -> None:
        """Usa a sessão aberta pelo serviço, sem abrir transação própria."""
        self._session = session

    async def create(
        self,
        *,
        token_hash: str,
        user_id: UUID,
        expires_at: datetime,
        user_agent: str,
    ) -> None:
        """Grava uma sessão nova. O id vem do padrão do banco, e o `flush()` envia o INSERT."""
        self._session.add(
            AuthSession(
                token_hash=token_hash,
                user_id=user_id,
                expires_at=expires_at,
                user_agent=user_agent,
            )
        )
        await self._session.flush()

    async def get_active(self, token_hash: str, now: datetime) -> AuthSession | None:
        """Devolve a sessão viva com este hash, ou `None`.

        Viva quer dizer não revogada e com `expires_at` depois de `now`. A busca usa o índice
        único de `token_hash`. `AsyncSession.scalar` executa a consulta e devolve a primeira
        coluna da primeira linha, aqui a entidade inteira, ou `None` sem linha.
        """
        return await self._session.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
        )

    async def revoke(self, token_hash: str, now: datetime) -> bool:
        """Revoga a sessão viva com este hash. Devolve se havia sessão viva para revogar.

        `UPDATE ... RETURNING id` devolve as linhas que mudaram. Como `token_hash` é único, há
        no máximo uma. Uma sessão já revogada ou expirada não muda, e o logout com ela vira 401.
        """
        result = await self._session.execute(
            update(AuthSession)
            .where(
                AuthSession.token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
            .values(revoked_at=now)
            .returning(AuthSession.id)
        )
        return result.scalar_one_or_none() is not None

    async def delete_for_user(self, user_id: UUID) -> None:
        """Apaga todas as sessões do usuário.

        Roda antes de apagar o usuário: `auth_sessions.user_id` não tem cascata, e a exclusão
        falharia com sessões no banco. Sem índice em `user_id`, o DELETE percorre a tabela; a
        Etapa 13.5 cria o índice.
        """
        await self._session.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
