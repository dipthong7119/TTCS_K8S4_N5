"""Restore the T-10 default for newly created connectors."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e9f7210b8c"
down_revision: str | None = "c7aa03e59214"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("connectors") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=20),
            existing_nullable=False,
            server_default="unavailable",
        )


def downgrade() -> None:
    with op.batch_alter_table("connectors") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=20),
            existing_nullable=False,
            server_default="unknown",
        )
