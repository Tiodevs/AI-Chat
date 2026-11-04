"""Pedidos de titular pelo canal de privacidade. Seções 8.1 e 11.5.

Revision ID: 0007_data_subject_requests
Revises: 0006_audit_survives_account
Create Date: 2026-11-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.domain.privacy import REQUEST_STATUS_CHECK_SQL, REQUEST_TYPE_CHECK_SQL

revision: str = "0007_data_subject_requests"
down_revision: str | Sequence[str] | None = "0006_audit_survives_account"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_subject_requests",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("contact_email", sa.Text(), nullable=False),
        sa.Column("request_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.CheckConstraint(REQUEST_TYPE_CHECK_SQL, name="data_subject_requests_request_type"),
        sa.CheckConstraint(REQUEST_STATUS_CHECK_SQL, name="data_subject_requests_status"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="data_subject_requests_user_id_fkey",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="data_subject_requests_pkey"),
    )
    op.create_index("data_subject_requests_due_at_idx", "data_subject_requests", ["due_at"])


def downgrade() -> None:
    op.drop_index("data_subject_requests_due_at_idx", table_name="data_subject_requests")
    op.drop_table("data_subject_requests")
