"""request_id da mensagem, para o inspetor de qualidade. Seções 12 e 15.5.

Revision ID: 0009_message_request_id
Revises: 0008_retention_runs
Create Date: 2026-11-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_message_request_id"
down_revision: str | Sequence[str] | None = "0008_retention_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("request_id", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "request_id")
