"""SCRUM-90 / S-46: Create alerts table for operational monitoring."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261013_alerts"
down_revision: str = "h20261011_remote_start"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("charge_point_id", sa.Integer(), nullable=False),
        sa.Column("connector_id", sa.Integer(), nullable=True),
        sa.Column("alert_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="warning", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["charge_point_id"], ["charge_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_charge_point_id", "alerts", ["charge_point_id"], unique=False)
    op.create_index("ix_alerts_connector_id", "alerts", ["connector_id"], unique=False)
    op.create_index("ix_alerts_status", "alerts", ["status"], unique=False)
    op.create_index(
        "ix_alerts_cp_status_type",
        "alerts",
        ["charge_point_id", "status", "alert_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_alerts_cp_status_type", table_name="alerts")
    op.drop_index("ix_alerts_status", table_name="alerts")
    op.drop_index("ix_alerts_connector_id", table_name="alerts")
    op.drop_index("ix_alerts_charge_point_id", table_name="alerts")
    op.drop_table("alerts")
