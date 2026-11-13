"""Tabelas do canal WhatsApp: contatos, caixa de entrada, caixa de saída e repasse. Seção 30.7.

Camada de entidade de persistência (seção 6.2). `WhatsAppRepository` lê e grava as quatro
tabelas. Criadas na migração `0011_whatsapp`. O desenho é o do ADR-017: o webhook grava em
`whatsapp_inbound_events` e responde, o processador lê de lá, e tudo que sai passa por
`whatsapp_outbound_messages`.

Cada contato tem uma chave de convidado interna (`guest_key_id`), que nunca vira cookie. Ela
é a dona das conversas do contato, então a fila, os limites, o bloqueio por abuso e a
exclusão em cascata do atendimento valem sem regra nova (seção 30.7).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.handoff import check_sql
from app.domain.whatsapp import (
    InboundKind,
    InboundStatus,
    MessageType,
    OutboundKind,
    OutboundStatus,
)
from app.models.base import Base


class WhatsAppContact(Base):
    """Uma pessoa que escreveu pelo WhatsApp, identificada pelo BSUID (ADR-018).

    `identity` é o BSUID, ou `phone:<wa_id>` só quando a Meta não manda BSUID. `phone` é o
    `wa_id`, guardado como dado secundário (D-12): serve de reserva no envio e nunca vai para
    log, rastro, métrica, console ou exportação. Retenção: 30 dias depois de
    `last_inbound_at`, junto com a chave de convidado, as conversas e os atendimentos.
    """

    __tablename__ = "whatsapp_contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    identity: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Apagar a chave de convidado apaga o contato. A retenção e o APAGAR DADOS apagam a chave.
    guest_key_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("guest_keys.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    # A `LEGAL_DOCUMENT_VERSION` do último aviso enviado (seção 30.9.4).
    notice_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_inbound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WhatsAppInboundEvent(Base):
    """A caixa de entrada: um item do webhook por linha, sem duplicar (NFR-22).

    `body`, `identity` e `phone` são apagados quando o evento termina. O texto passa a viver
    só em `messages`. A linha some 7 dias depois de `received_at`, o prazo das novas
    tentativas da Meta.
    """

    __tablename__ = "whatsapp_inbound_events"
    __table_args__ = (
        CheckConstraint(check_sql("kind", InboundKind), name="whatsapp_inbound_kind"),
        CheckConstraint(check_sql("status", InboundStatus), name="whatsapp_inbound_status"),
        CheckConstraint(
            f"message_type IS NULL OR {check_sql('message_type', MessageType)}",
            name="whatsapp_inbound_message_type",
        ),
        Index(
            "whatsapp_inbound_pending_idx",
            "wa_timestamp",
            postgresql_where=text("status IN ('pending', 'processing')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    event_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    identity: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_identity: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    button_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    wamid: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wa_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WhatsAppOutboundMessage(Base):
    """A caixa de saída: cada mensagem a enviar, gravada na transação que a produziu.

    `payload` tem o texto e os botões e é apagado no status final. A linha some 7 dias depois
    de `updated_at` no status final.
    """

    __tablename__ = "whatsapp_outbound_messages"
    __table_args__ = (
        CheckConstraint(check_sql("kind", OutboundKind), name="whatsapp_outbound_kind"),
        CheckConstraint(check_sql("status", OutboundStatus), name="whatsapp_outbound_status"),
        Index(
            "whatsapp_outbound_pending_idx",
            "next_attempt_at",
            postgresql_where=text("status = 'pending'"),
        ),
        Index("whatsapp_outbound_message_id_idx", "message_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("whatsapp_contacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    handoff_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("handoffs.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    wamid: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    used_phone: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    error_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WhatsAppHandoffRelay(Base):
    """O cursor do repasse de um atendimento do WhatsApp (seção 30.5).

    O repasse lê o atendimento e grava, na mesma transação que avança este cursor, as
    mensagens de saída da equipe e de cada mudança de status. Assim cada mensagem e cada
    aviso saem uma vez, sem mexer no código do console nem da varredura.
    """

    __tablename__ = "whatsapp_handoff_relay"

    handoff_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("handoffs.id", ondelete="CASCADE"), primary_key=True
    )
    delivered_seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    announced_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    announced_assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
