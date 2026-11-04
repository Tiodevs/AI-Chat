"""Tabela data_subject_requests. Seção 8.1 do SDD."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.privacy import REQUEST_STATUS_CHECK_SQL, REQUEST_TYPE_CHECK_SQL
from app.models.base import Base


class DataSubjectRequest(Base):
    __tablename__ = "data_subject_requests"
    __table_args__ = (
        CheckConstraint(REQUEST_TYPE_CHECK_SQL, name="data_subject_requests_request_type"),
        CheckConstraint(REQUEST_STATUS_CHECK_SQL, name="data_subject_requests_status"),
        Index("data_subject_requests_due_at_idx", "due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # O pedido sobrevive à exclusão da conta: guarda-se 2 anos depois de fechado.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    contact_email: Mapped[str] = mapped_column(Text, nullable=False)
    request_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
