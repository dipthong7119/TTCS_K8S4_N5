"""S-48 / SCRUM-76: Create reservations table for driver charge point reservations."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261012_reservations"
down_revision: str = "h20261011_remote_start"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("charge_point_id", sa.Integer(), nullable=False),
        sa.Column("connector_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("id_tag", sa.String(length=50), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("expiry_date", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reject_reason", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["charge_point_id"], ["charge_points.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reservations_charge_point_id", "reservations", ["charge_point_id"])
    op.create_index("ix_reservations_user_id", "reservations", ["user_id"])
    op.create_index(
        "ix_reservations_cp_conn_status",
        "reservations",
        ["charge_point_id", "connector_id", "status"],
    )
    op.create_index(
        "uq_reservations_active_connector",
        "reservations",
        ["charge_point_id", "connector_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('accepted', 'pending')"),
        postgresql_where=sa.text("status IN ('accepted', 'pending')"),
    )


def downgrade() -> None:
    op.drop_index("uq_reservations_active_connector", table_name="reservations")
    op.drop_index("ix_reservations_cp_conn_status", table_name="reservations")
    op.drop_index("ix_reservations_user_id", table_name="reservations")
    op.drop_index("ix_reservations_charge_point_id", table_name="reservations")
    op.drop_table("reservations")
