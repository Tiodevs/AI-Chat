"""Tabela consent_records. Uma concessão nova é uma linha nova. Seção 8.1."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.registration import PURPOSE_CHECK_SQL, SOURCE_CHECK_SQL
from app.models.base import Base


class ConsentRecord(Base):
    __tablename__ = "consent_records"
    __table_args__ = (
        CheckConstraint(PURPOSE_CHECK_SQL, name="consent_records_purpose"),
        CheckConstraint(SOURCE_CHECK_SQL, name="consent_records_source"),
        Index("consent_records_user_id_idx", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    document_version: Mapped[str] = mapped_column(Text, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
