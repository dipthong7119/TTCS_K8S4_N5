"""Store occupancy pricing and charging-finished time."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261009_tariff_fees"
down_revision: str | None = "h20261007_needs_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "station_tariffs",
        sa.Column("occupancy_fee_vnd_per_minute", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "station_tariffs",
        sa.Column("grace_period_minutes", sa.Integer(), server_default="0", nullable=False),
    )
    with op.batch_alter_table("station_tariffs") as batch:
        batch.create_check_constraint(
            "ck_station_tariff_occupancy_fee_nonnegative",
            "occupancy_fee_vnd_per_minute >= 0",
        )
        batch.create_check_constraint(
            "ck_station_tariff_grace_nonnegative",
            "grace_period_minutes >= 0",
        )
    op.add_column(
        "charging_sessions",
        sa.Column("occupancy_started_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("charging_sessions", "occupancy_started_at")
    with op.batch_alter_table("station_tariffs") as batch:
        batch.drop_constraint("ck_station_tariff_grace_nonnegative", type_="check")
        batch.drop_constraint("ck_station_tariff_occupancy_fee_nonnegative", type_="check")
    op.drop_column("station_tariffs", "grace_period_minutes")
    op.drop_column("station_tariffs", "occupancy_fee_vnd_per_minute")
