"""Tabela `conversations`: uma conversa de perguntas e respostas. Seção 8.1 do SDD.

Camada de entidade de persistência (seção 6.2 do SDD). `ConversationRepository` cria, lista e
anexa conversas, `InsightsRepository` as lê para o admin, e `RetentionRepository` apaga as
vencidas. Criada na migração `0004_conversations`.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Conversation(Base):
    """Uma conversa de um membro ou de um convidado.

    O dono é `user_id` ou `guest_key_id`. A conversa de convidado ganha o `user_id` quando a
    pessoa conclui o cadastro (seção 7.2), e o `guest_key_id` vira nulo no mesmo `UPDATE`
    (Etapa 15.1). Conversas anexadas antes disso ainda têm os dois, e a regra de dono recusa
    a chave nelas. A tabela não guarda a última atividade: ela é a mensagem mais nova, ou
    `created_at` sem mensagens.

    Retenção (seção 11.6): conversa de membro, 12 meses depois da última atividade; de
    convidado, 30 dias. Em cascata, a de membro some com a conta, e a de convidado, com a
    chave de convidado.
    """

    __tablename__ = "conversations"
    __table_args__ = (
        # Pelo menos um dono (seção 8.1).
        CheckConstraint(
            "user_id IS NOT NULL OR guest_key_id IS NOT NULL",
            name="conversations_owner",
        ),
        # O canal da conversa, `web` ou `whatsapp` (seção 30.7, migração `0011_whatsapp`).
        CheckConstraint("channel IN ('web', 'whatsapp')", name="conversations_channel"),
        # B-tree da seção 8.2, para a lista de conversas do membro. Não há índice em
        # `guest_key_id`; a Etapa 13.5 cria um.
        Index("conversations_user_id_idx", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    # `ondelete="CASCADE"`: apagar a chave de convidado apaga as conversas dela. Antes disso,
    # a retenção solta a chave das conversas que já viraram de membro.
    guest_key_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("guest_keys.id", ondelete="CASCADE"),
        nullable=True,
    )
    # Sem padrão no banco. O serviço grava `allocate_conversation_created_at`: o horário atual
    # ou, se ele não passa da conversa mais nova, um microssegundo depois dela.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # `whatsapp` quando a conversa nasceu no canal WhatsApp: o dono é a chave de convidado
    # interna do contato, que nunca vira cookie (seção 30.7).
    channel: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'web'"))
