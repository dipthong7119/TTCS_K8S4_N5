"""SCRUM-117: Đảm bảo charge_points có cột last_seen_at cho Heartbeat.

Cung cấp guard idempotent để thêm cột nếu chưa có.
Tham chiếu: 02_DAC_TA_DU_AN.md (Heartbeat).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "h20261002_t17_heartbeat"
down_revision: str | None = "h20261002_t16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {col["name"] for col in inspector.get_columns("charge_points")}

    # Thêm cột last_seen_at nếu chưa có
    if "last_seen_at" not in existing:
        op.add_column(
            "charge_points",
            sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {col["name"] for col in inspector.get_columns("charge_points")}

    if "last_seen_at" in existing:
        op.drop_column("charge_points", "last_seen_at")
