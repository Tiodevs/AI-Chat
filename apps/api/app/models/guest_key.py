"""Tabela `guest_keys`: a chave das conversas de quem não entrou. Seções 8.1 e 10.3 do SDD.

Camada de entidade de persistência (seção 6.2 do SDD). `ConversationRepository` cria e procura
as chaves, e `RetentionRepository` apaga as vencidas. Criada na migração `0004_conversations`.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GuestKey(Base):
    """A chave de um convidado, para a conversa anônima sobreviver a uma atualização da página.

    O cookie `atrium_guest` guarda o segredo e dura 30 dias. O banco guarda só o SHA-256 dele.
    Retenção: a chave some 30 dias depois de criada, e as conversas de convidado ligadas a ela
    vão junto, pela cascata de `conversations.guest_key_id` (seção 11.6).
    """

    __tablename__ = "guest_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # SHA-256 em hexadecimal do segredo do cookie. O índice da restrição única serve a busca.
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # Sem padrão no banco: o serviço grava o horário do `Clock`. A retenção conta daqui.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
