"""Tabela `attendant_acknowledgements`: o aceite do compromisso da equipe. Seção 29.3 do SDD.

Camada de entidade de persistência (seção 6.2). `HandoffRepository` grava o aceite de
`POST /v1/attendance/acknowledgement` e confere a versão vigente antes de assumir. Criada na
migração `0010_handoffs`.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AttendantAcknowledgement(Base):
    """O aceite de uma versão do compromisso de confidencialidade (seção 29.3).

    A chave primária é `(user_id, version)`: a pessoa aceita de novo a cada versão nova de
    `ATTENDANT_TERMS_VERSION`. Retenção: enquanto a conta existir (seção 29.9.9).
    """

    __tablename__ = "attendant_acknowledgements"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    version: Mapped[str] = mapped_column(Text, primary_key=True)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
