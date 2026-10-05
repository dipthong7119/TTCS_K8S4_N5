"""S-04/S-05: new stations are inactive and connector status is unknown."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261004_defaults"
down_revision: str = "h20261004_merge_boot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("stations") as batch_op:
        batch_op.alter_column("status", existing_type=sa.String(20), server_default="inactive")
    with op.batch_alter_table("connectors") as batch_op:
        batch_op.alter_column("status", existing_type=sa.String(20), server_default="unknown")


def downgrade() -> None:
    with op.batch_alter_table("connectors") as batch_op:
        batch_op.alter_column("status", existing_type=sa.String(20), server_default="unavailable")
    with op.batch_alter_table("stations") as batch_op:
        batch_op.alter_column("status", existing_type=sa.String(20), server_default="active")
