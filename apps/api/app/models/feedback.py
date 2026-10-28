"""Tabela feedback. Uma nota por mensagem. Seção 8.1 do SDD."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (CheckConstraint("rating IN (-1, 1)", name="feedback_rating"),)

    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
