"""Atendimento humano: atendimentos, presença, aceite do compromisso e colunas novas.

Revision ID: 0010_handoffs
Revises: 0009_message_request_id
Create Date: 2026-11-12

Seção 29.7 do SDD, Etapa 17.2. Cria:

- `handoffs`: um atendimento por pedido do visitante, com status, motivo da oferta, quem
  assumiu, motivo do encerramento, os instantes da fila e o contador `last_seq` da retomada.
  O índice único parcial em `conversation_id`, onde o status não é `closed`, garante um
  atendimento ativo por conversa.
- `attendant_presence`: uma linha por pessoa da equipe, com `available` ou `away` e o último
  sinal do console.
- `attendant_acknowledgements`: o aceite de cada versão do compromisso de confidencialidade.

E muda, em expand and contract (seção 22.1), sem reescrever linhas antigas:

- `users.role` aceita `attendant`;
- `messages` ganha `handoff_id`, `seq`, `author_user_id`, `redaction` e `redacted_at`, todos
  anuláveis, e `role` aceita `attendant`. Uma mensagem com `handoff_id` é do atendimento.

As listas de valores ficam escritas aqui, e não importadas do domínio, para esta revisão não
mudar quando um enum mudar. O downgrade apaga o que a revisão criou; um banco com mensagens
de `attendant` ou contas `attendant` precisa apagá-las antes, porque as restrições antigas
voltam.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_handoffs"
down_revision: str | Sequence[str] | None = "0009_message_request_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TRIGGERS = "'abstained', 'grounding_failed', 'off_topic', 'degraded', 'error', 'not_helpful'"
_CLOSE_REASONS = (
    "'resolved', 'redirected', 'out_of_scope', 'no_response', 'abusive', "
    "'visitor_cancelled', 'visitor_ended', 'queue_timeout', 'visitor_left', "
    "'service_closed', 'inactivity'"
)
_REDACTIONS = "'health', 'document', 'contact', 'third_party', 'other', 'retention'"


def upgrade() -> None:
    """Cria as três tabelas e acrescenta as colunas e restrições novas."""
    # 1. O papel novo das contas da equipe.
    op.drop_constraint("users_role", "users", type_="check")
    op.create_check_constraint("users_role", "users", "role IN ('member', 'admin', 'attendant')")

    op.create_table(
        "handoffs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("trigger_message_id", sa.Uuid(), nullable=True),
        sa.Column("attendant_id", sa.Uuid(), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("visitor_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seq", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("content_purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('queued', 'assigned', 'closed')", name="handoffs_status"),
        sa.CheckConstraint(f"trigger IN ({_TRIGGERS})", name="handoffs_trigger"),
        sa.CheckConstraint(
            f"close_reason IS NULL OR close_reason IN ({_CLOSE_REASONS})",
            name="handoffs_close_reason",
        ),
        # `assigned` sempre tem quem assumiu, e `closed` sempre tem motivo e instante.
        sa.CheckConstraint(
            "status <> 'assigned' OR attendant_id IS NOT NULL",
            name="handoffs_assigned_attendant",
        ),
        sa.CheckConstraint(
            "status <> 'closed' OR (close_reason IS NOT NULL AND closed_at IS NOT NULL)",
            name="handoffs_closed_reason",
        ),
        sa.CheckConstraint("last_seq >= 0", name="handoffs_last_seq"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="handoffs_conversation_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trigger_message_id"],
            ["messages.id"],
            name="handoffs_trigger_message_id_fkey",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["attendant_id"],
            ["users.id"],
            name="handoffs_attendant_id_fkey",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="handoffs_pkey"),
    )
    # Um atendimento ativo por conversa (seção 29.7).
    op.create_index(
        "handoffs_active_conversation_idx",
        "handoffs",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'closed'"),
    )
    # A fila anda por `requested_at` (seção 29.5).
    op.create_index("handoffs_status_requested_at_idx", "handoffs", ["status", "requested_at"])
    # Os atendimentos de cada pessoa, para a capacidade e o console.
    op.create_index(
        "handoffs_attendant_id_idx",
        "handoffs",
        ["attendant_id"],
        postgresql_where=sa.text("status = 'assigned'"),
    )
    # A retenção do texto, 90 dias depois do encerramento (seção 29.9.9).
    op.create_index("handoffs_closed_at_idx", "handoffs", ["closed_at"])

    # 2. As colunas novas de `messages`, todas anuláveis: só o catálogo muda.
    op.add_column("messages", sa.Column("handoff_id", sa.Uuid(), nullable=True))
    op.add_column("messages", sa.Column("seq", sa.Integer(), nullable=True))
    op.add_column("messages", sa.Column("author_user_id", sa.Uuid(), nullable=True))
    op.add_column("messages", sa.Column("redaction", sa.Text(), nullable=True))
    op.add_column("messages", sa.Column("redacted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "messages_handoff_id_fkey",
        "messages",
        "handoffs",
        ["handoff_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint("messages_role", "messages", type_="check")
    op.create_check_constraint(
        "messages_role", "messages", "role IN ('user', 'assistant', 'attendant')"
    )
    op.create_check_constraint(
        "messages_attendant_handoff",
        "messages",
        "role <> 'attendant' OR handoff_id IS NOT NULL",
    )
    op.create_check_constraint(
        "messages_handoff_seq", "messages", "handoff_id IS NULL OR seq IS NOT NULL"
    )
    op.create_check_constraint(
        "messages_redaction",
        "messages",
        f"redaction IS NULL OR redaction IN ({_REDACTIONS})",
    )
    # O cursor da retomada: um `seq` por mensagem do atendimento (seção 29.6).
    op.create_unique_constraint("messages_handoff_id_seq_key", "messages", ["handoff_id", "seq"])

    op.create_table(
        "attendant_presence",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('available', 'away')", name="attendant_presence_status"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="attendant_presence_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="attendant_presence_pkey"),
    )
    op.create_table(
        "attendant_acknowledgements",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="attendant_acknowledgements_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "version", name="attendant_acknowledgements_pkey"),
    )


def downgrade() -> None:
    """Apaga as tabelas e colunas novas e volta as restrições de papel."""
    op.drop_table("attendant_acknowledgements")
    op.drop_table("attendant_presence")
    op.drop_constraint("messages_handoff_id_seq_key", "messages", type_="unique")
    op.drop_constraint("messages_redaction", "messages", type_="check")
    op.drop_constraint("messages_handoff_seq", "messages", type_="check")
    op.drop_constraint("messages_attendant_handoff", "messages", type_="check")
    op.drop_constraint("messages_role", "messages", type_="check")
    op.create_check_constraint("messages_role", "messages", "role IN ('user', 'assistant')")
    op.drop_constraint("messages_handoff_id_fkey", "messages", type_="foreignkey")
    op.drop_column("messages", "redacted_at")
    op.drop_column("messages", "redaction")
    op.drop_column("messages", "author_user_id")
    op.drop_column("messages", "seq")
    op.drop_column("messages", "handoff_id")
    op.drop_index("handoffs_closed_at_idx", table_name="handoffs")
    op.drop_index("handoffs_attendant_id_idx", table_name="handoffs")
    op.drop_index("handoffs_status_requested_at_idx", table_name="handoffs")
    op.drop_index("handoffs_active_conversation_idx", table_name="handoffs")
    op.drop_table("handoffs")
    op.drop_constraint("users_role", "users", type_="check")
    op.create_check_constraint("users_role", "users", "role IN ('member', 'admin')")
