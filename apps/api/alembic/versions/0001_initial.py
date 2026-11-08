"""Tabelas iniciais e a extensão vector.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-26

Primeira revisão. Cria a extensão `vector` do pgvector, de que a coluna de embedding da
`0002_corpus` depende, e as tabelas de contas, sessões, limites e auditoria da seção 8.1:

- `users`: e-mail único e em minúsculas, papel `member` ou `admin` e `visitor_type` restrito
  à lista da seção 8.1, tudo conferido também pelo banco. A regra de `visit_reason` só entra
  na `0005_registration`.
- `auth_sessions`: só o SHA-256 do segredo do cookie, nunca o segredo (seção 10.3). Falta
  índice em `user_id`; a Etapa 13.5 o cria.
- `rate_limit_windows`: a janela fixa dos limites de taxa, com chave primária
  `(bucket_key, window_start)` (seção 10.4).
- `audit_events`: nasce com chave estrangeira para `users`, que a
  `0006_audit_survives_account` tira.

Os ids usam `gen_random_uuid()`, nativo do PostgreSQL desde a versão 13, e as datas são
`timestamptz` (seção 8). A chave de `auth_sessions.user_id` não tem `ondelete`: a exclusão
de conta e o `bootstrap_admin --remove` apagam as sessões antes do usuário. O downgrade
apaga as quatro tabelas e a extensão.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria a extensão `vector` e as tabelas de contas, sessões, limites e auditoria."""
    # `IF NOT EXISTS` aceita um banco em que a extensão já foi criada. A imagem
    # `pgvector/pgvector`, da CI e da Railway, traz a extensão instalada (seção 22.1).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("visitor_type", sa.Text(), nullable=True),
        sa.Column("visit_reason", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Regras da seção 8.1 também no banco: e-mail em minúsculas, papel e tipo de visitante.
        sa.CheckConstraint("email = lower(email)", name="users_email_lowercase"),
        sa.CheckConstraint("role IN ('member', 'admin')", name="users_role"),
        sa.CheckConstraint(
            "visitor_type IS NULL OR visitor_type IN ('patient', 'visitor', 'caregiver')",
            name="users_visitor_type",
        ),
        sa.PrimaryKeyConstraint("id", name="users_pkey"),
        sa.UniqueConstraint("email", name="users_email_key"),
    )
    # O cookie guarda o segredo; o banco, só o SHA-256 dele, único (seção 8.1).
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="auth_sessions_user_id_fkey"),
        sa.PrimaryKeyConstraint("id", name="auth_sessions_pkey"),
        sa.UniqueConstraint("token_hash", name="auth_sessions_token_hash_key"),
    )
    # Uma linha por balde e janela. `bucket_key` já vem como HMAC, nunca com o IP cru (8.1).
    op.create_table(
        "rate_limit_windows",
        sa.Column("bucket_key", sa.Text(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("bucket_key", "window_start", name="rate_limit_windows_pkey"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="audit_events_actor_user_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="audit_events_pkey"),
    )


def downgrade() -> None:
    """Apaga as quatro tabelas, na ordem inversa das chaves, e depois a extensão."""
    op.drop_table("audit_events")
    op.drop_table("rate_limit_windows")
    op.drop_table("auth_sessions")
    op.drop_table("users")
    # Sem `CASCADE`: só funciona porque o downgrade da `0002_corpus` já apagou `chunks`, a
    # única coluna do tipo `vector`.
    op.execute("DROP EXTENSION IF EXISTS vector")
