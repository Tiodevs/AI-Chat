"""Tabela `retention_runs`: uma linha por regra a cada execução do `retention-job`.

Camada de entidade de persistência (seção 6.2 do SDD). `RetentionRepository.record_run` grava a
linha na mesma transação que apaga, e `OpsMetricsRepository` a lê para as métricas
`atrium_retention_*`. Criada na migração `0008_retention_runs`. Seções 8.1 e 18.3 do SDD.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RetentionRun(Base):
    """O resultado de uma regra de retenção numa execução.

    O job roda em outro processo, que o Prometheus não coleta. Por isso o `/metrics` da API
    lê esta tabela (seção 18.3). A linha não guarda dado pessoal, e nenhuma regra apaga esta
    tabela.
    """

    __tablename__ = "retention_runs"
    # Serve ao `max(ran_at)` da métrica de última execução.
    __table_args__ = (Index("retention_runs_ran_at_idx", "ran_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Um valor de `RetentionRule`, como `guest_conversations`.
    rule: Mapped[str] = mapped_column(Text, nullable=False)
    # Linhas que a regra apagou diretamente. O que sumiu em cascata não entra na conta.
    deleted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
