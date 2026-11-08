"""Tabela `data_subject_requests`: os pedidos de titular do canal de privacidade.

Camada de entidade de persistência (seção 6.2 do SDD). `PrivacyRequestRepository` grava, lista
e trava os pedidos, `OpsMetricsRepository` conta os abertos para o `/metrics`, e
`RetentionRepository` apaga os fechados há 2 anos. Criada na migração
`0007_data_subject_requests`. Seções 8.1 e 11.5 do SDD.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.privacy import REQUEST_STATUS_CHECK_SQL, REQUEST_TYPE_CHECK_SQL
from app.models.base import Base


class DataSubjectRequest(Base):
    """Um pedido de titular, com prazo de 15 dias corridos (seção 11.5).

    Qualquer pessoa abre um pedido, com ou sem sessão. Um pedido fechado (`done` ou
    `rejected`) não muda mais. Retenção: o pedido some 2 anos depois de fechado, e um pedido
    aberto nunca vence (seção 11.6).
    """

    __tablename__ = "data_subject_requests"
    __table_args__ = (
        # Listas fechadas dos enums `RequestType` e `RequestStatus` do domínio.
        CheckConstraint(REQUEST_TYPE_CHECK_SQL, name="data_subject_requests_request_type"),
        CheckConstraint(REQUEST_STATUS_CHECK_SQL, name="data_subject_requests_status"),
        # A fila do admin ordena os abertos pelo prazo. A seção 8.2 pede um B-tree em
        # `status`, mas a migração `0007` criou este em `due_at`, e não há índice em `status`.
        Index("data_subject_requests_due_at_idx", "due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # O pedido sobrevive à exclusão da conta: guarda-se 2 anos depois de fechado.
    # `ondelete="SET NULL"` zera o vínculo quando a conta some. Com o vínculo nulo, a fila do
    # admin mostra `linked_account` falso.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # O endereço pelo qual o admin responde. A validação de um endereço só fica no domínio.
    contact_email: Mapped[str] = mapped_column(Text, nullable=False)
    request_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # `open`, `in_progress`, `done` ou `rejected`.
    status: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # `received_at` mais 15 dias. Aberto com `due_at` no passado é atrasado.
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Gravado ao fechar. A regra de retenção conta daqui.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Obrigatória para fechar, regra do domínio. Não entra na auditoria.
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
