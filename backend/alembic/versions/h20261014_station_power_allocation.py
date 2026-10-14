"""SCRUM-80/81/82: persist station and connector power limits."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261014_station_power_allocation"
down_revision: str | None = "h20261013_payment_refunds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("stations") as batch:
        batch.add_column(sa.Column("power_limit_kw", sa.Numeric(10, 3), nullable=True))
        batch.create_check_constraint(
            "ck_stations_power_limit_positive",
            "power_limit_kw IS NULL OR power_limit_kw > 0",
        )

    with op.batch_alter_table("connectors") as batch:
        batch.add_column(sa.Column("rated_power_kw", sa.Numeric(10, 3), nullable=True))
        batch.create_check_constraint(
            "ck_connectors_rated_power_positive",
            "rated_power_kw IS NULL OR rated_power_kw > 0",
        )

    with op.batch_alter_table("charging_sessions") as batch:
        batch.add_column(sa.Column("requested_power_limit_w", sa.Integer(), nullable=True))
        batch.create_check_constraint(
            "ck_charging_sessions_power_limit_nonnegative",
            "requested_power_limit_w IS NULL OR requested_power_limit_w >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("charging_sessions") as batch:
        batch.drop_constraint("ck_charging_sessions_power_limit_nonnegative", type_="check")
        batch.drop_column("requested_power_limit_w")

    with op.batch_alter_table("connectors") as batch:
        batch.drop_constraint("ck_connectors_rated_power_positive", type_="check")
        batch.drop_column("rated_power_kw")

    with op.batch_alter_table("stations") as batch:
        batch.drop_constraint("ck_stations_power_limit_positive", type_="check")
        batch.drop_column("power_limit_kw")
