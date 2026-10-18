"""S-47: tìm trạm gần — thêm connector_type cho connectors,
thêm chỉ mục tìm nhanh trạm theo status + toạ độ.

Tiến: thêm cột connectors.connector_type (nullable),
      thêm index ix_stations_status_latlon,
      thêm index ix_connectors_cp_type_status.
Lùi: xoá cột và các chỉ mục.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261015_s47_nearby"
down_revision: str = "h20261014_reservations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Thêm cột connector_type vào bảng connectors (dùng batch cho SQLite)
    with op.batch_alter_table("connectors") as batch:
        batch.add_column(
            sa.Column(
                "connector_type",
                sa.String(length=50),
                nullable=True,
            )
        )
        # Chỉ mục phụ: tra cứu theo trụ + loại + trạng thái (gom nhóm connector_types)
        batch.create_index(
            "ix_connectors_cp_type_status",
            ["charge_point_id", "connector_type", "status"],
        )

    # 2. Thêm chỉ mục tìm trạm theo status + latitude + longitude
    #    (bounding box trước khi haversine chính xác)
    op.create_index(
        "ix_stations_status_latlon",
        "stations",
        ["status", "latitude", "longitude"],
    )


def downgrade() -> None:
    # Xoá chỉ mục trạm
    op.drop_index("ix_stations_status_latlon", table_name="stations")

    # Xoá chỉ mục và cột connector_type
    with op.batch_alter_table("connectors") as batch:
        batch.drop_index("ix_connectors_cp_type_status")
        batch.drop_column("connector_type")
