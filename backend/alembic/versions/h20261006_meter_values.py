"""T-40: reconcile the existing meter_values foreign key and lookup index."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261006_meter_values"
down_revision: str = "h20261004_defaults"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_FK_NAMING = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
_OLD_INDEX = "ix_meter_values_session_measured"
_NEW_INDEX = "ix_meter_values_session_id_measured_at"


def _set_session_foreign_key(ondelete: str) -> None:
    foreign_key = next(
        key for key in sa.inspect(op.get_bind()).get_foreign_keys("meter_values")
        if key["constrained_columns"] == ["session_id"]
    )
    if foreign_key.get("options", {}).get("ondelete") == ondelete:
        return
    name = foreign_key["name"] or "fk_meter_values_session_id_charging_sessions"
    with op.batch_alter_table("meter_values", naming_convention=_FK_NAMING) as batch:
        batch.drop_constraint(name, type_="foreignkey")
        batch.create_foreign_key(
            "fk_meter_values_session_id", "charging_sessions", ["session_id"], ["id"],
            ondelete=ondelete,
        )


def _replace_index(source: str, target: str) -> None:
    names = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("meter_values")}
    if target not in names:
        op.create_index(target, "meter_values", ["session_id", "measured_at"], unique=False)
    if source in names:
        op.drop_index(source, table_name="meter_values")


def upgrade() -> None:
    # The table and any saved samples belong to the earlier session migration.
    _set_session_foreign_key("RESTRICT")
    _replace_index(_OLD_INDEX, _NEW_INDEX)


def downgrade() -> None:
    _replace_index(_NEW_INDEX, _OLD_INDEX)
    _set_session_foreign_key("CASCADE")
