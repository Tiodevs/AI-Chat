"""Tabela `feedback`: a nota do visitante para uma resposta. Seções 8.1 e 12 do SDD.

Camada de entidade de persistência (seção 6.2 do SDD). `ConversationRepository` grava e lê as
notas, e `InsightsRepository` as conta para o admin. Criada na migração `0004_conversations`.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Feedback(Base):
    """Útil ou não útil, uma vez por resposta do assistente.

    A tabela não guarda quem avaliou: o dono vem da conversa da mensagem. Que a mensagem seja
    do assistente é regra do serviço, não do banco. Retenção: some com a mensagem (seção 11.6).
    """

    __tablename__ = "feedback"
    # `1` é útil e `-1` é não útil.
    __table_args__ = (CheckConstraint("rating IN (-1, 1)", name="feedback_rating"),)

    # A chave primária é a própria mensagem, então uma segunda nota viola a chave. O serviço
    # transforma esse erro num 409: a nota vale uma vez (seção 12).
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
