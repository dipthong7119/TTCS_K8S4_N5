"""T-16/T-17: đảm bảo charge_points có các cột cần thiết cho BootNotification.

Revision ID: h20261004_boot_notification
Revises: a6d2f891c104
Create Date: 2026-10-04 16:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'h20261004_boot_notification'
down_revision: str | None = 'a6d2f891c104'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_columns = {col["name"] for col in inspector.get_columns("charge_points")}

    with op.batch_alter_table("charge_points") as batch_op:
        if "vendor" not in existing_columns:
            batch_op.add_column(sa.Column("vendor", sa.String(255), nullable=True))
        if "model" not in existing_columns:
            batch_op.add_column(sa.Column("model", sa.String(255), nullable=True))
        if "firmware_version" not in existing_columns:
            batch_op.add_column(sa.Column("firmware_version", sa.String(100), nullable=True))
        if "status" not in existing_columns:
            batch_op.add_column(sa.Column("status", sa.String(20), server_default="offline", nullable=False))
        if "last_seen_at" not in existing_columns:
            batch_op.add_column(sa.Column("last_seen_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Các cột này thuộc về schema chuẩn, migration này chỉ mang tính idempotent guard,
    # nên khi downgrade chúng ta không drop chúng để tránh mất dữ liệu của hệ thống.
    pass
