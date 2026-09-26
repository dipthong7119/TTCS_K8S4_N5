"""Start new connectors in the unknown state required by S-05."""

import sqlalchemy as sa

from alembic import op

revision = "b37ad56c90e1"
down_revision = "9f2c6a1b7d40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("connectors") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=20),
            existing_nullable=False,
            server_default="unknown",
        )


def downgrade() -> None:
    with op.batch_alter_table("connectors") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=20),
            existing_nullable=False,
            server_default="unavailable",
        )
