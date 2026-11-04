"""Execuções do retention-job, para a métrica e o alerta de retenção parada. Seção 18.3.

Revision ID: 0008_retention_runs
Revises: 0007_data_subject_requests
Create Date: 2026-11-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_retention_runs"
down_revision: str | Sequence[str] | None = "0007_data_subject_requests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "retention_runs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("deleted_count", sa.Integer(), nullable=False),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="retention_runs_pkey"),
    )
    op.create_index("retention_runs_ran_at_idx", "retention_runs", ["ran_at"])


def downgrade() -> None:
    op.drop_index("retention_runs_ran_at_idx", table_name="retention_runs")
    op.drop_table("retention_runs")
