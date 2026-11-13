"""Tabela `handoffs`: o atendimento humano de uma conversa. Seção 29.7 do SDD.

Camada de entidade de persistência (seção 6.2). `HandoffRepository` lê e grava a tabela, a
varredura (`services/handoff_sweep.py`) muda o status por `UPDATE` condicional, e a retenção
apaga o texto das mensagens dos encerrados há 90 dias. Criada na migração `0010_handoffs`.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.handoff import CloseReason, HandoffStatus, HandoffTrigger, check_sql
from app.models.base import Base


class Handoff(Base):
    """Um atendimento: da fila até o encerramento, sem voltar de `closed` (seção 29.5).

    Retenção (seção 29.9.9): o registro fica com a conversa e some em cascata com ela. O
    texto das mensagens some 90 dias depois de `closed_at`, e `content_purged_at` registra
    quando. `attendant_id` vira nulo se a conta da pessoa da equipe for apagada, e a autoria
    das mensagens continua em `messages.author_user_id`.
    """

    __tablename__ = "handoffs"
    __table_args__ = (
        CheckConstraint(check_sql("status", HandoffStatus), name="handoffs_status"),
        CheckConstraint(check_sql("trigger", HandoffTrigger), name="handoffs_trigger"),
        CheckConstraint(
            f"close_reason IS NULL OR {check_sql('close_reason', CloseReason)}",
            name="handoffs_close_reason",
        ),
        CheckConstraint(
            "status <> 'assigned' OR attendant_id IS NOT NULL",
            name="handoffs_assigned_attendant",
        ),
        CheckConstraint(
            "status <> 'closed' OR (close_reason IS NOT NULL AND closed_at IS NOT NULL)",
            name="handoffs_closed_reason",
        ),
        CheckConstraint("last_seq >= 0", name="handoffs_last_seq"),
        CheckConstraint("channel IN ('web', 'whatsapp')", name="handoffs_channel"),
        # Um atendimento ativo por conversa (seção 29.7).
        Index(
            "handoffs_active_conversation_idx",
            "conversation_id",
            unique=True,
            postgresql_where=text("status <> 'closed'"),
        ),
        Index("handoffs_status_requested_at_idx", "status", "requested_at"),
        Index(
            "handoffs_attendant_id_idx",
            "attendant_id",
            postgresql_where=text("status = 'assigned'"),
        ),
        Index("handoffs_closed_at_idx", "closed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    # O desfecho que motivou a oferta (seção 29.4).
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    # A resposta do assistente que motivou o pedido. Nula se a mensagem sumir.
    trigger_message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    attendant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A fila anda por `requested_at`, que não muda quando o atendimento volta para a fila.
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Recomeça a cada volta para a fila: a espera máxima de 15 minutos conta daqui.
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # A última mensagem, de qualquer ponta. O atendimento parado há 30 minutos encerra.
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # O último tique do fluxo do visitante. Sem fluxo há 5 minutos, a fila encerra.
    visitor_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # O último `seq` gravado. Cada mensagem nova, e cada remoção, soma 1 (seção 29.6).
    last_seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    content_purged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # O canal da conversa, copiado no pedido. O console mostra o selo WhatsApp por ele.
    channel: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'web'"))
