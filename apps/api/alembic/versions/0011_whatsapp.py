"""Canal WhatsApp: contatos, caixa de entrada, caixa de saída, repasse e o canal da conversa.

Revision ID: 0011_whatsapp
Revises: 0010_handoffs
Create Date: 2026-11-12

Seção 30.7 do SDD, Etapa 18.2. Cria:

- `whatsapp_contacts`: uma pessoa do WhatsApp, pelo BSUID, com a chave de convidado interna
  que é dona das conversas dela e o telefone como dado secundário (ADR-018, D-12).
- `whatsapp_inbound_events`: a caixa de entrada do webhook, com a chave única que impede o
  processamento repetido (ADR-017, NFR-22).
- `whatsapp_outbound_messages`: a caixa de saída, com o status de entrega.
- `whatsapp_handoff_relay`: o cursor do repasse do atendimento para o WhatsApp.

E acrescenta, em expand and contract, `conversations.channel` e `handoffs.channel`, os dois
com o padrão `web`, sem reescrever linhas antigas. As listas de valores ficam escritas aqui,
como na `0010_handoffs`. O downgrade apaga o que a revisão criou.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_whatsapp"
down_revision: str | Sequence[str] | None = "0010_handoffs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHANNELS = "'web', 'whatsapp'"


def upgrade() -> None:
    """Cria as quatro tabelas e as colunas de canal."""
    op.add_column(
        "conversations",
        sa.Column("channel", sa.Text(), server_default=sa.text("'web'"), nullable=False),
    )
    op.create_check_constraint(
        "conversations_channel", "conversations", f"channel IN ({_CHANNELS})"
    )
    op.add_column(
        "handoffs",
        sa.Column("channel", sa.Text(), server_default=sa.text("'web'"), nullable=False),
    )
    op.create_check_constraint("handoffs_channel", "handoffs", f"channel IN ({_CHANNELS})")

    op.create_table(
        "whatsapp_contacts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("identity", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("guest_key_id", sa.Uuid(), nullable=False),
        sa.Column("notice_version", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guest_key_id"], ["guest_keys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identity"),
        sa.UniqueConstraint("guest_key_id"),
    )

    op.create_table(
        "whatsapp_inbound_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_key", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("identity", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("previous_identity", sa.Text(), nullable=True),
        sa.Column("message_type", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("button_id", sa.Text(), nullable=True),
        sa.Column("wamid", sa.Text(), nullable=True),
        sa.Column("delivery_status", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Integer(), nullable=True),
        sa.Column("wa_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('message', 'status', 'system')", name="whatsapp_inbound_kind"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'failed', 'ignored')",
            name="whatsapp_inbound_status",
        ),
        sa.CheckConstraint(
            "message_type IS NULL OR message_type IN ('text', 'button', 'media', 'other')",
            name="whatsapp_inbound_message_type",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key"),
    )
    op.create_index(
        "whatsapp_inbound_pending_idx",
        "whatsapp_inbound_events",
        ["wa_timestamp"],
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
    )

    op.create_table(
        "whatsapp_outbound_messages",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("handoff_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("wamid", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("used_phone", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('text', 'buttons', 'notice', 'status_update')",
            name="whatsapp_outbound_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'delivered', 'read', 'failed')",
            name="whatsapp_outbound_status",
        ),
        sa.ForeignKeyConstraint(["contact_id"], ["whatsapp_contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["handoff_id"], ["handoffs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wamid"),
    )
    op.create_index(
        "whatsapp_outbound_pending_idx",
        "whatsapp_outbound_messages",
        ["next_attempt_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "whatsapp_outbound_message_id_idx", "whatsapp_outbound_messages", ["message_id"]
    )

    op.create_table(
        "whatsapp_handoff_relay",
        sa.Column("handoff_id", sa.Uuid(), nullable=False),
        sa.Column("delivered_seq", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("announced_status", sa.Text(), nullable=True),
        sa.Column("announced_assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["handoff_id"], ["handoffs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("handoff_id"),
    )


def downgrade() -> None:
    """Apaga as tabelas e as colunas de canal, na ordem inversa."""
    op.drop_table("whatsapp_handoff_relay")
    op.drop_index("whatsapp_outbound_message_id_idx", table_name="whatsapp_outbound_messages")
    op.drop_index("whatsapp_outbound_pending_idx", table_name="whatsapp_outbound_messages")
    op.drop_table("whatsapp_outbound_messages")
    op.drop_index("whatsapp_inbound_pending_idx", table_name="whatsapp_inbound_events")
    op.drop_table("whatsapp_inbound_events")
    op.drop_table("whatsapp_contacts")
    op.drop_constraint("handoffs_channel", "handoffs", type_="check")
    op.drop_column("handoffs", "channel")
    op.drop_constraint("conversations_channel", "conversations", type_="check")
    op.drop_column("conversations", "channel")
