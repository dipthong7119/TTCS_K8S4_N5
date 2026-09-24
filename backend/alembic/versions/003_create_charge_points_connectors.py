"""create_charge_points_connectors

Revision ID: 003_create_charge_points_connectors
Revises: 002_create_stations
Create Date: 2026-09-24

Task T-10 — Sprint 1
Tạo hai bảng con của stations theo quan hệ cha-con hai tầng:
  stations → charge_points → connectors

AC:  chèn hai trụ cùng code thì DB từ chối (UNIQUE constraint).
NFR: charge_points.code UNIQUE toàn hệ thống + chỉ mục (tra cứu OCPP).
     connectors.connector_id bắt đầu từ 1, khớp với connectorId trong OCPP 1.6J.
"""

import sqlalchemy as sa
from alembic import op

# Revision identifiers
revision: str = "003_create_charge_points_connectors"
down_revision = "002_create_stations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Bảng charge_points ───────────────────────────────────────────────────
    op.create_table(
        "charge_points",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # code UNIQUE toàn hệ thống — mọi kết nối OCPP tra cứu theo cột này (T-10 NFR)
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("vendor", sa.String(255), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("firmware_version", sa.String(100), nullable=True),
        # Trạng thái kết nối OCPP: online | offline
        sa.Column("status", sa.String(20), nullable=False, server_default="offline"),
        # Thời điểm nhận tin nhắn cuối — dùng bởi job offline-detector (T-26)
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["station_id"],
            ["stations.id"],
            name="fk_charge_points_station_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("code", name="uq_charge_points_code"),
    )

    op.create_index("ix_charge_points_id", "charge_points", ["id"])
    # Chỉ mục tường minh trên code — đây là cột tra cứu chính trong OCPP gateway
    op.create_index("ix_charge_points_code", "charge_points", ["code"], unique=True)
    op.create_index("ix_charge_points_station_id", "charge_points", ["station_id"])

    # ── Bảng connectors ──────────────────────────────────────────────────────
    op.create_table(
        "connectors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("charge_point_id", sa.Integer(), nullable=False),
        # Số thứ tự đầu nối bắt đầu từ 1 — khớp connectorId trong OCPP 1.6J (T-10 NFR)
        sa.Column("connector_id", sa.Integer(), nullable=False),
        # Trạng thái theo OCPP 1.6J StatusNotification
        sa.Column("status", sa.String(20), nullable=False, server_default="Unavailable"),
        sa.Column("error_code", sa.String(50), nullable=False, server_default="NoError"),
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
        sa.ForeignKeyConstraint(
            ["charge_point_id"],
            ["charge_points.id"],
            name="fk_connectors_charge_point_id",
            ondelete="CASCADE",
        ),
        # Ràng buộc: không trùng connector_id trong cùng một trụ (T-10 AC)
        sa.UniqueConstraint(
            "charge_point_id", "connector_id", name="uq_connectors_cp_connector"
        ),
    )

    op.create_index("ix_connectors_id", "connectors", ["id"])
    op.create_index("ix_connectors_charge_point_id", "connectors", ["charge_point_id"])


def downgrade() -> None:
    # Xoá child trước, parent sau
    op.drop_index("ix_connectors_charge_point_id", table_name="connectors")
    op.drop_index("ix_connectors_id", table_name="connectors")
    op.drop_table("connectors")

    op.drop_index("ix_charge_points_station_id", table_name="charge_points")
    op.drop_index("ix_charge_points_code", table_name="charge_points")
    op.drop_index("ix_charge_points_id", table_name="charge_points")
    op.drop_table("charge_points")
