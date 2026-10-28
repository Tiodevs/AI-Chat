"""Conversas, mensagens, feedback e a chave de convidado.

Revision ID: 0004_conversations
Revises: 0003_token_usage
Create Date: 2026-10-27

Os B-tree de messages.conversation_id e conversations.user_id entram com as
tabelas. Seções 8.1 e 8.2 do SDD.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.domain.outcomes import OUTCOME_CHECK_SQL

revision: str = "0004_conversations"
down_revision: str | Sequence[str] | None = "0003_token_usage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guest_keys",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="guest_keys_pkey"),
        sa.UniqueConstraint("token_hash", name="guest_keys_token_hash_key"),
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("guest_key_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "user_id IS NOT NULL OR guest_key_id IS NOT NULL",
            name="conversations_owner",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="conversations_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["guest_key_id"],
            ["guest_keys.id"],
            name="conversations_guest_key_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="conversations_pkey"),
    )
    op.create_index("conversations_user_id_idx", "conversations", ["user_id"], unique=False)
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("client_message_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", JSONB(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("langsmith_run_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="messages_role"),
        sa.CheckConstraint(OUTCOME_CHECK_SQL, name="messages_outcome"),
        sa.CheckConstraint("input_tokens >= 0 AND output_tokens >= 0", name="messages_tokens"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="messages_conversation_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="messages_pkey"),
        sa.UniqueConstraint(
            "conversation_id",
            "client_message_id",
            name="messages_conversation_id_client_message_id_key",
        ),
    )
    op.create_index("messages_conversation_id_idx", "messages", ["conversation_id"], unique=False)
    op.create_table(
        "feedback",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("rating IN (-1, 1)", name="feedback_rating"),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name="feedback_message_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("message_id", name="feedback_pkey"),
    )


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_index("messages_conversation_id_idx", table_name="messages")
    op.drop_table("messages")
    op.drop_index("conversations_user_id_idx", table_name="conversations")
    op.drop_table("conversations")
    op.drop_table("guest_keys")
