"""Tabela `auth_sessions`: as sessões de quem entrou. Seções 8.1 e 10.3 do SDD.

Camada de entidade de persistência (seção 6.2 do SDD). `AuthSessionRepository` cria, procura e
revoga sessões, e `RetentionRepository` apaga as vencidas. Criada na migração `0001_initial`.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuthSession(Base):
    """Uma sessão aberta pelo login ou pela conclusão do cadastro.

    O cookie `atrium_session` guarda um segredo de 256 bits, e o banco guarda só o SHA-256
    dele. Quem lê a tabela não consegue montar um cookie válido. A sessão dura 14 dias, e sair
    grava `revoked_at` (seção 10.3). Retenção: a linha some 14 dias depois de expirar ou de ser
    revogada (seção 11.6). A tabela não tem `created_at`.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # SHA-256 em hexadecimal. O índice da restrição única serve a busca de cada pedido.
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # Sem `ondelete`: apagar o usuário falharia com sessões dele no banco. Por isso a
    # exclusão da conta e a retenção apagam as sessões antes do usuário. Também não há índice
    # nesta coluna; a Etapa 13.5 cria um.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # O user agent do navegador, sem byte nulo e cortado em 512 caracteres
    # (`clean_user_agent`). Serve à segurança (seção 11.3).
    user_agent: Mapped[str] = mapped_column(Text, nullable=False)
