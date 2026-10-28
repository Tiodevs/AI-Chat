"""Tabela registration_sessions. A transcrição não guarda senha. Seção 8.1."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.registration import PATH_CHECK_SQL, STATUS_CHECK_SQL
from app.models.base import Base


class RegistrationSession(Base):
    __tablename__ = "registration_sessions"
    __table_args__ = (
        CheckConstraint(STATUS_CHECK_SQL, name="registration_sessions_status"),
        CheckConstraint(PATH_CHECK_SQL, name="registration_sessions_path"),
        Index("registration_sessions_user_id_idx", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
