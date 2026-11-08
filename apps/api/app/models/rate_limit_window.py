"""Tabela rate_limit_windows. A chave é o HMAC do IP, nunca o IP cru. Seção 8.1 do SDD.

Camada de entidade de persistência (seção 6.2 do SDD). `RateLimitRepository.increment` conta os
pedidos de cada balde da seção 10.4, e `RetentionRepository` apaga as janelas com mais de 48
horas. Criada na migração `0001_initial`.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RateLimitWindow(Base):
    """Um contador de pedidos para um balde numa janela fixa de tempo.

    A chave primária composta `(bucket_key, window_start)` faz cada balde ter uma linha por
    janela. Ficar no PostgreSQL faz o limite valer para todas as réplicas (seção 6.5).
    Retenção: 48 horas (seção 11.6).
    """

    __tablename__ = "rate_limit_windows"

    # `{finalidade}:{HMAC-SHA256}`, de `bucket_key` no domínio. O HMAC usa `RATE_LIMIT_HMAC_KEY`
    # e leva o dia UTC como sal, então nem o IP nem o e-mail ficam gravados, e a chave do mesmo
    # IP muda a cada dia.
    bucket_key: Mapped[str] = mapped_column(Text, primary_key=True)
    # Início da janela, alinhado ao tamanho dela (`fixed_window_start`).
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
