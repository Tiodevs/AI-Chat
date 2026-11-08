"""Sessão de cadastro e registros de consentimento. Seções 7.2 e 8.1.

Revision ID: 0005_registration
Revises: 0004_conversations
Create Date: 2026-10-28

Cria o que o cadastro da seção 7.2 grava:

- a restrição `users_visit_reason`, com a lista de motivos de `app.domain.fields` (seção 8.5);
- `consent_records`: uma linha por concessão, com finalidade e origem restritas às listas de
  `app.domain.registration`. Revogar grava `revoked_at`, e conceder de novo cria outra linha
  (seção 8.1). Apagar o usuário apaga os consentimentos dele;
- `registration_sessions`: o estado da máquina, os campos e a transcrição em `jsonb` e o hash
  da senha, nunca a senha. O id vem do serviço, não do banco, e `user_id` só é preenchido na
  conclusão.

As listas das restrições vêm do código atual: um valor novo, como uma finalidade, pede uma
revisão que troque a restrição nos bancos existentes. O downgrade apaga as duas tabelas e a
restrição.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.domain.fields import VISIT_REASON_CHECK_SQL
from app.domain.registration import (
    PATH_CHECK_SQL,
    PURPOSE_CHECK_SQL,
    SOURCE_CHECK_SQL,
    STATUS_CHECK_SQL,
)

revision: str = "0005_registration"
down_revision: str | Sequence[str] | None = "0004_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Restringe `users.visit_reason` e cria `consent_records` e `registration_sessions`."""
    # A restrição entra numa tabela que já existe: o banco confere as linhas atuais.
    op.create_check_constraint("users_visit_reason", "users", VISIT_REASON_CHECK_SQL)
    op.create_table(
        "consent_records",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("document_version", sa.Text(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.CheckConstraint(PURPOSE_CHECK_SQL, name="consent_records_purpose"),
        sa.CheckConstraint(SOURCE_CHECK_SQL, name="consent_records_source"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="consent_records_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="consent_records_pkey"),
    )
    op.create_index("consent_records_user_id_idx", "consent_records", ["user_id"], unique=False)
    # Sem `server_default` no id: o serviço gera o UUID. A retenção apaga a linha pelo
    # `expires_at` (seção 11.6).
    op.create_table(
        "registration_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("fields", JSONB(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("transcript", JSONB(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(STATUS_CHECK_SQL, name="registration_sessions_status"),
        sa.CheckConstraint(PATH_CHECK_SQL, name="registration_sessions_path"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="registration_sessions_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="registration_sessions_pkey"),
    )
    op.create_index(
        "registration_sessions_user_id_idx",
        "registration_sessions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Apaga as duas tabelas, com os consentimentos, e tira a restrição de `visit_reason`."""
    op.drop_index("registration_sessions_user_id_idx", table_name="registration_sessions")
    op.drop_table("registration_sessions")
    op.drop_index("consent_records_user_id_idx", table_name="consent_records")
    op.drop_table("consent_records")
    op.drop_constraint("users_visit_reason", "users", type_="check")
