"""Reconcile the reservation schema and join the active feature histories."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261016_integrate_feature_heads"
down_revision: tuple[str, str, str] = (
    "h20261015_s47_nearby",
    "h20261013_audit_target_user",
    "h20261015_merge_resv_heads",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_LEDGER_CHECK = (
    "(entry_type IN ('manual_topup', 'demo_topup', 'sandbox_topup', 'refund') "
    "AND amount_vnd > 0) OR "
    "(entry_type IN ('session_charge', 'subscription_charge', 'payment_refund', "
    "'no_show_fee') AND amount_vnd < 0) OR "
    "(entry_type = 'adjustment' AND amount_vnd != 0)"
)


def _columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _names(table_name: str) -> set[str | None]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return set()
    checks = inspector.get_check_constraints(table_name)
    foreign_keys = inspector.get_foreign_keys(table_name)
    return {item.get("name") for item in checks + foreign_keys}


def _indexes(table_name: str) -> dict[str, list[str]]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return {}
    return {
        item["name"]: list(item.get("column_names") or [])
        for item in inspector.get_indexes(table_name)
        if item.get("name")
    }


def _upgrade_legacy_s52_reservations() -> None:
    columns = _columns("reservations")
    if not columns or "charge_point_id" in columns:
        return

    required_legacy = {"driver_user_id", "connector_id", "expiry_at", "id_tag_id"}
    if not required_legacy.issubset(columns):
        raise RuntimeError(
            "Không nhận diện được schema reservations cũ; dừng migration để giữ dữ liệu an toàn"
        )

    # The standalone S-52 branch used connector_id for connectors.id. The
    # integrated API uses connector_id for the OCPP number, so keep the old PK
    # in connector_db_id and introduce the protocol number separately.
    with op.batch_alter_table("reservations") as batch:
        batch.alter_column(
            "driver_user_id",
            new_column_name="user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch.alter_column(
            "connector_id",
            new_column_name="connector_db_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch.alter_column(
            "expiry_at",
            new_column_name="expiry_date",
            existing_type=sa.DateTime(),
            nullable=False,
        )
        batch.add_column(sa.Column("charge_point_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("connector_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("id_tag", sa.String(50), nullable=True))
        batch.add_column(sa.Column("start_time", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("reject_reason", sa.String(100), nullable=True))
        batch.add_column(
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            )
        )

    op.execute(
        sa.text(
            "UPDATE reservations SET charge_point_id = ("
            "SELECT c.charge_point_id FROM connectors c "
            "WHERE c.id = reservations.connector_db_id) "
            "WHERE charge_point_id IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE reservations SET connector_id = ("
            "SELECT c.connector_id FROM connectors c "
            "WHERE c.id = reservations.connector_db_id) "
            "WHERE connector_id IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE reservations SET id_tag = ("
            "SELECT t.id_tag FROM id_tags t WHERE t.id = reservations.id_tag_id) "
            "WHERE id_tag IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE reservations SET start_time = created_at WHERE start_time IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE reservations SET updated_at = created_at WHERE created_at IS NOT NULL"
        )
    )
    op.execute(sa.text("UPDATE reservations SET status = 'accepted' WHERE status = 'active'"))
    op.execute(sa.text("UPDATE reservations SET status = 'completed' WHERE status = 'fulfilled'"))

    unresolved = op.get_bind().execute(
        sa.text(
            "SELECT COUNT(*) FROM reservations WHERE charge_point_id IS NULL "
            "OR connector_id IS NULL OR id_tag IS NULL OR start_time IS NULL"
        )
    ).scalar_one()
    if unresolved:
        raise RuntimeError(
            f"Có {unresolved} reservation cũ thiếu connector hoặc idTag; "
            "đã dừng migration để giữ nguyên dữ liệu"
        )

    constraints = _names("reservations")
    with op.batch_alter_table("reservations") as batch:
        for column_name, column_type in (
            ("charge_point_id", sa.Integer()),
            ("connector_id", sa.Integer()),
            ("id_tag", sa.String(50)),
            ("start_time", sa.DateTime()),
        ):
            batch.alter_column(
                column_name,
                existing_type=column_type,
                nullable=False,
            )
        if "fk_reservations_charge_point_id_charge_points" not in constraints:
            batch.create_foreign_key(
                "fk_reservations_charge_point_id_charge_points",
                "charge_points",
                ["charge_point_id"],
                ["id"],
                ondelete="CASCADE",
            )
        if "ck_reservation_status" in constraints:
            batch.drop_constraint("ck_reservation_status", type_="check")
        batch.create_check_constraint(
            "ck_reservation_status",
            "status IN ('pending', 'accepted', 'rejected', 'expired', 'cancelled', 'completed')",
        )

    indexes = _indexes("reservations")
    desired = {
        "ix_reservations_charge_point_id": ["charge_point_id"],
        "ix_reservations_user_id": ["user_id"],
        "ix_reservations_cp_conn_status": [
            "charge_point_id",
            "connector_id",
            "status",
        ],
        "uq_reservations_active_connector": ["charge_point_id", "connector_id"],
    }
    for name, columns in desired.items():
        if name in indexes and indexes[name] != columns:
            op.drop_index(name, table_name="reservations")
            indexes.pop(name)
        if name not in indexes:
            op.create_index(
                name,
                "reservations",
                columns,
                unique=name == "uq_reservations_active_connector",
                postgresql_where=(
                    sa.text("status IN ('accepted', 'pending')")
                    if name == "uq_reservations_active_connector"
                    else None
                ),
                sqlite_where=(
                    sa.text("status IN ('accepted', 'pending')")
                    if name == "uq_reservations_active_connector"
                    else None
                ),
            )


def _set_wallet_constraint() -> None:
    constraints = _names("wallet_ledger")
    with op.batch_alter_table("wallet_ledger") as batch:
        if "ck_wallet_ledger_amount_sign" in constraints:
            batch.drop_constraint("ck_wallet_ledger_amount_sign", type_="check")
        batch.create_check_constraint("ck_wallet_ledger_amount_sign", _LEDGER_CHECK)


def upgrade() -> None:
    _upgrade_legacy_s52_reservations()
    _set_wallet_constraint()


def downgrade() -> None:
    raise RuntimeError(
        "Migration hợp nhất schema đặt chỗ không hỗ trợ downgrade tự động; "
        "hãy dùng backup trước khi khôi phục phiên bản cũ"
    )
