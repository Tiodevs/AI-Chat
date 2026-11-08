"""Conversas, mensagens, feedback e a chave de convidado.

Revision ID: 0004_conversations
Revises: 0003_token_usage
Create Date: 2026-10-27

Os B-tree de messages.conversation_id e conversations.user_id entram com as
tabelas. Seções 8.1 e 8.2 do SDD.

Cria as tabelas das perguntas (seções 7.1 e 8.1):

- `guest_keys`: o SHA-256 do segredo do cookie `atrium_guest`, para uma conversa anônima
  sobreviver a uma atualização da página.
- `conversations`: o dono é o usuário ou a chave de convidado, e `conversations_owner` exige
  pelo menos um. Apagar o usuário ou a chave apaga a conversa (`ondelete="CASCADE"`), o que
  serve à exclusão da conta e à retenção (seção 11.6).
- `messages`: o par `(conversation_id, client_message_id)` é único, e é ele que faz o
  reenvio responder 409 sem chamar o modelo (seção 7.1). As respostas do assistente têm
  `client_message_id` nulo, e o PostgreSQL não compara nulos numa restrição única.
  `outcome` aceita só os desfechos de `app.domain.outcomes`.
- `feedback`: uma nota por mensagem, `-1` ou `1`, com a mensagem como chave primária, o que
  faz a segunda nota responder 409.

`OUTCOME_CHECK_SQL` vem do código atual: um desfecho novo pede uma revisão que troque a
restrição `messages_outcome` dos bancos que já existem. `messages_conversation_id_idx` repete
o começo da restrição única, e falta índice em `conversations.guest_key_id`; a Etapa 13.5
ajusta os dois. O downgrade apaga as quatro tabelas e as conversas com elas.
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
    """Cria `guest_keys`, `conversations`, `messages` e `feedback`."""
    # O `created_at` destas tabelas não tem padrão no banco: o serviço grava o horário do
    # relógio que recebeu.
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
    # Redundante com o começo da restrição única acima; a Etapa 13.5 o remove.
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
    """Apaga as quatro tabelas, das dependentes para as donas, com as conversas e o feedback."""
    op.drop_table("feedback")
    op.drop_index("messages_conversation_id_idx", table_name="messages")
    op.drop_table("messages")
    op.drop_index("conversations_user_id_idx", table_name="conversations")
    op.drop_table("conversations")
    op.drop_table("guest_keys")
