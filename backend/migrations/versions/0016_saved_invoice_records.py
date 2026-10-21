"""Store encrypted owner-scoped invoice clients and catalog items."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_saved_invoice_records"
down_revision: str | None = "0015_dynamic_qr_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table, index in (
        ("saved_invoice_clients", "ix_saved_invoice_clients_owner_created"),
        ("saved_invoice_items", "ix_saved_invoice_items_owner_created"),
    ):
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column(
                "encrypted_data",
                sa.String(length=4096 if table.endswith("clients") else 2048),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
        op.create_index(index, table, ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("saved_invoice_items")
    op.drop_table("saved_invoice_clients")
