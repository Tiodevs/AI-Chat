"""Tabela `attendant_presence`: se a pessoa da equipe está disponível. Seção 29.7 do SDD.

Camada de entidade de persistência (seção 6.2). `HandoffRepository` grava o status marcado no
console e o sinal de cada tique do fluxo do console, e lê a presença para a disponibilidade.
Criada na migração `0010_handoffs`.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.handoff import PresenceStatus, check_sql
from app.models.base import Base


class AttendantPresence(Base):
    """Uma linha por pessoa da equipe, sem histórico (seção 29.7).

    Presente é `available` com sinal nos últimos 45 segundos (seção 29.4). Retenção: a linha
    some com o papel, pelo script `attendants revoke`, ou em cascata com a conta.
    """

    __tablename__ = "attendant_presence"
    __table_args__ = (
        CheckConstraint(check_sql("status", PresenceStatus), name="attendant_presence_status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
