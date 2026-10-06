"""Align the existing meter_values table with the model."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261006_meter_values"
down_revision: str = "h20261004_defaults"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _change_foreign_key(ondelete: str) -> None:
    inspector = sa.inspect(op.get_bind())
    foreign_key = next(
        fk
        for fk in inspector.get_foreign_keys("meter_values")
        if fk["constrained_columns"] == ["session_id"]
    )
    convention = {
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    }
    old_name = (
        foreign_key["name"]
        or "fk_meter_values_session_id_charging_sessions"
    )
    with op.batch_alter_table(
        "meter_values", naming_convention=convention
    ) as batch:
        batch.drop_constraint(old_name, type_="foreignkey")
        batch.create_foreign_key(
            "fk_meter_values_session_id",
            "charging_sessions",
            ["session_id"],
            ["id"],
            ondelete=ondelete,
        )


def upgrade() -> None:
    _change_foreign_key("RESTRICT")
    op.drop_index(
        "ix_meter_values_session_measured", table_name="meter_values"
    )
    op.create_index(
        "ix_meter_values_session_id_measured_at",
        "meter_values",
        ["session_id", "measured_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_meter_values_session_id_measured_at", table_name="meter_values"
    )
    _change_foreign_key("CASCADE")
    op.create_index(
        "ix_meter_values_session_measured",
        "meter_values",
        ["session_id", "measured_at"],
    )