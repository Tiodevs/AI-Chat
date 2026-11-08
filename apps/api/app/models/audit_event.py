"""Tabela `audit_events`: quem fez o quê nas ações que a auditoria cobre. Seção 8.1 do SDD.

Camada de entidade de persistência (seção 6.2 do SDD). `AuditRepository.record` grava os
eventos dos serviços de documentos, qualidade, fila de titular e conta, e `RetentionRepository`
apaga os que têm mais de 2 anos. Criada na migração `0001_initial`; a `0006` tirou a chave
estrangeira.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditEvent(Base):
    """Um evento de auditoria, como `document.upload`, `identity.reveal` ou `account.delete`.

    A lista das ações está na seção 8.1. O evento guarda ids e, em algumas ações, um motivo,
    sem e-mail nem conteúdo de conversa. Retenção: 2 anos (seção 11.6).
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Sem chave estrangeira: a auditoria sobrevive à exclusão da conta. Seção 11.6.
    # A migração `0006_audit_survives_account` removeu a que existia: `account.delete` grava
    # o id de quem acabou de ser apagado.
    actor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    # O tipo do alvo (`document`, `conversation`, `data_subject_request`, `consent`, `user`)
    # e o id dele. Também sem chave estrangeira, porque o alvo varia.
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    # O motivo do `identity.reveal`, a troca de status do `dsr.update` (`open->in_progress`)
    # ou a mudança do `consent.change`. Nulo nas outras ações.
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
