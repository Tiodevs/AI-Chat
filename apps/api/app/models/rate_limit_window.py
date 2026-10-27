"""Tabela rate_limit_windows. A chave é o HMAC do IP, nunca o IP cru. Seção 8.1 do SDD."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RateLimitWindow(Base):
    __tablename__ = "rate_limit_windows"

    bucket_key: Mapped[str] = mapped_column(Text, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
