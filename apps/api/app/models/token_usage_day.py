"""Tabela token_usage_days. Seção 8.1 do SDD."""

from datetime import date

from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TokenUsageDay(Base):
    __tablename__ = "token_usage_days"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
