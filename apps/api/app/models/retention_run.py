"""Tabela retention_runs. Seção 8.1 do SDD."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RetentionRun(Base):
    __tablename__ = "retention_runs"
    __table_args__ = (Index("retention_runs_ran_at_idx", "ran_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    rule: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
