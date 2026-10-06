"""T-37: Create meter_values table."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql import func
from alembic import op

revision: str = "h20261006_meter_values"
down_revision: str = "h20261004_defaults"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meter_values",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("measured_at", sa.DateTime(), nullable=False),
        sa.Column("measurand", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["charging_sessions.id"],
            name="fk_meter_values_session_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_meter_values"),
    )
    op.create_index(
        "ix_meter_values_session_id_measured_at",
        "meter_values",
        ["session_id", "measured_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_meter_values_session_id_measured_at", table_name="meter_values")
    op.drop_table("meter_values")
