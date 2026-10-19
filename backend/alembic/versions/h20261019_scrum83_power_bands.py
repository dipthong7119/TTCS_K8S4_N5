"""SCRUM-83: Add station power-limit time bands.

Revision ID: h20261019_scrum83_power_bands
Revises: h20261018_demo_driver_2
Create Date: 2026-10-19 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261019_scrum83_power_bands"
down_revision: str | None = "h20261018_demo_driver_2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("station_power_bands"):
        op.create_table(
            "station_power_bands",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "station_id",
                sa.Integer(),
                sa.ForeignKey("stations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("start_minute", sa.Integer(), nullable=False),
            sa.Column("end_minute", sa.Integer(), nullable=False),
            sa.Column("power_limit_kw", sa.Numeric(10, 3), nullable=False),
            sa.CheckConstraint(
                "start_minute >= 0 AND start_minute < 1440",
                name="ck_station_power_bands_start_minute",
            ),
            sa.CheckConstraint(
                "end_minute >= 0 AND end_minute <= 1440",
                name="ck_station_power_bands_end_minute",
            ),
            sa.CheckConstraint(
                "start_minute <> end_minute",
                name="ck_station_power_bands_nonempty",
            ),
            sa.CheckConstraint(
                "power_limit_kw > 0",
                name="ck_station_power_bands_limit_positive",
            ),
            sa.UniqueConstraint(
                "station_id", "start_minute", name="uq_station_power_band_start"
            ),
        )
    else:
        # Some existing volumes already contain this table from an earlier
        # schema, while alembic_version still points at the parent revision.
        # Reconcile that table in place instead of failing with DuplicateTable.
        existing_columns = {
            column["name"] for column in inspector.get_columns("station_power_bands")
        }
        required_columns = {
            "id",
            "station_id",
            "start_minute",
            "end_minute",
            "power_limit_kw",
        }
        missing_columns = required_columns - existing_columns
        if missing_columns:
            raise RuntimeError(
                "station_power_bands exists but is missing required columns: "
                + ", ".join(sorted(missing_columns))
            )

        check_names = {
            constraint["name"]
            for constraint in inspector.get_check_constraints("station_power_bands")
        }

        # An earlier version required end_minute > start_minute, which rejected
        # bands that wrap past midnight. Replace that check with the current
        # range and non-empty checks. Adding the new checks also validates any
        # existing rows before Alembic records this revision.
        if "ck_station_power_band_minutes" in check_names:
            op.drop_constraint(
                "ck_station_power_band_minutes",
                "station_power_bands",
                type_="check",
            )
            check_names.remove("ck_station_power_band_minutes")

        expected_checks = {
            "ck_station_power_bands_start_minute":
                "start_minute >= 0 AND start_minute < 1440",
            "ck_station_power_bands_end_minute":
                "end_minute >= 0 AND end_minute <= 1440",
            "ck_station_power_bands_nonempty": "start_minute <> end_minute",
            "ck_station_power_bands_limit_positive": "power_limit_kw > 0",
        }
        for name, condition in expected_checks.items():
            if name not in check_names:
                op.create_check_constraint(name, "station_power_bands", condition)

        unique_constraints = {
            constraint["name"]
            for constraint in inspector.get_unique_constraints("station_power_bands")
        }
        if "uq_station_power_band_start" not in unique_constraints:
            op.create_unique_constraint(
                "uq_station_power_band_start",
                "station_power_bands",
                ["station_id", "start_minute"],
            )

    # Existing versions used the same index name without end_minute. Rebuild
    # it when its columns do not match the model's lookup order.
    expected_index_columns = ["station_id", "start_minute", "end_minute"]
    indexes = {
        index["name"]: index.get("column_names")
        for index in sa.inspect(bind).get_indexes("station_power_bands")
    }
    index_columns = indexes.get("ix_station_power_bands_station_minutes")
    if index_columns is not None and index_columns != expected_index_columns:
        op.drop_index(
            "ix_station_power_bands_station_minutes",
            table_name="station_power_bands",
        )
        index_columns = None
    if index_columns is None:
        op.create_index(
            "ix_station_power_bands_station_minutes",
            "station_power_bands",
            expected_index_columns,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_station_power_bands_station_minutes",
        table_name="station_power_bands",
    )
    op.drop_table("station_power_bands")
