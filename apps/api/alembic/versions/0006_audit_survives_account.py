"""A auditoria sobrevive à exclusão da conta. Seções 8.1 e 11.6.

`account.delete` guarda só o id de quem excluiu, e o usuário deixa de existir.
O vínculo com `users` impediria a exclusão, então a chave estrangeira sai.

Revision ID: 0006_audit_survives_account
Revises: 0005_registration
Create Date: 2026-11-03

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_audit_survives_account"
down_revision: str | Sequence[str] | None = "0005_registration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_events_actor_user_id_fkey")


def downgrade() -> None:
    op.execute("DELETE FROM audit_events WHERE actor_user_id NOT IN (SELECT id FROM users)")
    op.create_foreign_key(
        "audit_events_actor_user_id_fkey",
        "audit_events",
        "users",
        ["actor_user_id"],
        ["id"],
    )
