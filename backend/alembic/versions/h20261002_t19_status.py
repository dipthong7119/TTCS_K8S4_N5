"""SCRUM-119: Đảm bảo bảng connectors có các cột status và ocpp_status.

Cung cấp guard idempotent để thêm cột nếu chưa có.
Tham chiếu: 02_DAC_TA_DU_AN.md (StatusNotification).
"""

from collections.abc import Sequence

import sqlalchemy as sa
<<<<<<< HEAD
=======

>>>>>>> 8cf926d056b9e2b97c0e961073b67f863da7c728
from alembic import op

revision: str = "h20261002_t19_status"
down_revision: str | None = "h20261002_t17_heartbeat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {col["name"] for col in inspector.get_columns("connectors")}

    # Thêm cột status nếu chưa có
    if "status" not in existing:
        op.add_column(
            "connectors",
            sa.Column("status", sa.String(20), server_default="unavailable", nullable=False),
        )

    # Thêm cột ocpp_status (raw_status) nếu chưa có
    if "ocpp_status" not in existing:
        op.add_column(
            "connectors",
            sa.Column("ocpp_status", sa.String(50), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {col["name"] for col in inspector.get_columns("connectors")}

    if "ocpp_status" in existing:
        op.drop_column("connectors", "ocpp_status")
<<<<<<< HEAD
        
    if "status" in existing:
        op.drop_column("connectors", "status")
=======

    # Do NOT drop 'status' because it was created in 0003_create_charge_points
>>>>>>> 8cf926d056b9e2b97c0e961073b67f863da7c728
