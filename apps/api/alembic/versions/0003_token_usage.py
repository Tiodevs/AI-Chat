"""Contador diário de tokens.

Revision ID: 0003_token_usage
Revises: 0002_corpus
Create Date: 2026-10-27

Seção 8.1 do SDD.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_token_usage"
down_revision: str | Sequence[str] | None = "0002_corpus"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "token_usage_days",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("day", name="token_usage_days_pkey"),
    )


def downgrade() -> None:
    op.drop_table("token_usage_days")
