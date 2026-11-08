"""request_id da mensagem, para o inspetor de qualidade. Seções 12 e 15.5.

Revision ID: 0009_message_request_id
Revises: 0008_retention_runs
Create Date: 2026-11-04

Acrescenta `messages.request_id`, anulável: o `request_id` do pedido que gravou a mensagem,
que o inspetor de qualidade mostra para achar o log e o rastro (seções 8.1 e 18.5). As linhas
antigas ficam com `NULL`, e o código anterior continua funcionando, como pede o expand and
contract (seção 22.1). O downgrade apaga a coluna e os valores dela.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_message_request_id"
down_revision: str | Sequence[str] | None = "0008_retention_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Acrescenta a coluna anulável `messages.request_id`."""
    # Anulável e sem padrão: o PostgreSQL só muda o catálogo, sem reescrever a tabela.
    op.add_column("messages", sa.Column("request_id", sa.Text(), nullable=True))


def downgrade() -> None:
    """Apaga a coluna `messages.request_id`."""
    op.drop_column("messages", "request_id")
