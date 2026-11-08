"""Tabela `consent_records`: o histórico de cada consentimento. Seções 7.2 e 8.1 do SDD.

Camada de entidade de persistência (seção 6.2 do SDD). `ConsentRepository` grava e lê as
linhas. O cadastro grava os aceites, a página da conta concede e revoga, e o inspetor do admin
consulta o consentimento de melhoria. Criada na migração `0005_registration`.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.registration import PURPOSE_CHECK_SQL, SOURCE_CHECK_SQL
from app.models.base import Base


class ConsentRecord(Base):
    """Uma concessão de uma finalidade, numa versão dos documentos legais.

    A tabela só cresce: revogar grava `revoked_at` na linha vigente, e conceder de novo cria
    uma linha nova. Por isso não há restrição única por usuário e finalidade. O histórico é a
    prova do consentimento (seção 11.3). Retenção: enquanto a conta existir (seção 11.6).
    """

    __tablename__ = "consent_records"
    __table_args__ = (
        # As listas fechadas vêm dos enums `Purpose` e `ConsentSource` do domínio do cadastro.
        CheckConstraint(PURPOSE_CHECK_SQL, name="consent_records_purpose"),
        CheckConstraint(SOURCE_CHECK_SQL, name="consent_records_source"),
        # B-tree da seção 8.2. Toda consulta da tabela filtra por usuário.
        Index("consent_records_user_id_idx", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # `ondelete="CASCADE"`: os registros somem com a conta (seção 11.6).
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # `terms_and_privacy_notice`, `age_18_plus`, `profile_personalization` ou
    # `quality_improvement`.
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    # A `LEGAL_DOCUMENT_VERSION` vigente quando a pessoa concedeu. Uma versão nova dos Termos
    # pede novo aceite (seção 11.11).
    document_version: Mapped[str] = mapped_column(Text, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Nulo enquanto a concessão vale.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Onde a pessoa concedeu: `chat`, `form` ou `account`.
    source: Mapped[str] = mapped_column(Text, nullable=False)
