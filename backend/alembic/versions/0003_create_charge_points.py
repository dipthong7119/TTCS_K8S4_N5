"""
Migration: tao bang charge_points va connectors
Tham chieu: SPRINT_1.md T-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_create_charge_points"
down_revision = "0002_create_stations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Bang charge_points -----------------------------------------------
    op.create_table(
        "charge_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        # UNIQUE + INDEX: moi ket noi WebSocket OCPP tra cuu theo cot nay (T-10 NFR)
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column(
            "station_id",
            sa.Integer(),
            sa.ForeignKey("stations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vendor", sa.String(255), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("firmware_version", sa.String(100), nullable=True),
        # online | offline
        sa.Column("status", sa.String(20), server_default="offline", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # Chi muc rieng tren code de tra cuu OCPP nhanh (T-10 NFR)
    op.create_index("ix_charge_points_code", "charge_points", ["code"], unique=True)

    # -- Bang connectors --------------------------------------------------
    op.create_table(
        "connectors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "charge_point_id",
            sa.Integer(),
            sa.ForeignKey("charge_points.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Khop voi connectorId trong giao thuc OCPP, bat dau tu 1 (T-10 NFR)
        sa.Column("connector_id", sa.Integer(), nullable=False),
        # unavailable | available | charging | faulted
        sa.Column("status", sa.String(20), server_default="unavailable", nullable=False),
        sa.Column("error_code", sa.String(50), server_default="NoError", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        # DB tu choi neu chen hai dau noi cung tru cung so (T-10 AC)
        sa.UniqueConstraint("charge_point_id", "connector_id", name="uq_connector_per_charge_point"),
    )


def downgrade() -> None:
    op.drop_table("connectors")
    op.drop_index("ix_charge_points_code", table_name="charge_points")
    op.drop_table("charge_points")
