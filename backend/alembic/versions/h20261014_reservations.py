"""S-52: extend the existing reservation table with expiry and fee state."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261014_reservations"
down_revision: str | None = "h20261015_merge_heads_pr96"
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


def _constraint_names(table_name: str) -> set[str | None]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return set()
    return {
        item.get("name")
        for item in (
            inspector.get_check_constraints(table_name)
            + inspector.get_foreign_keys(table_name)
        )
    }


def _index_columns(table_name: str) -> dict[str, list[str]]:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return {}
    return {
        item["name"]: list(item.get("column_names") or [])
        for item in inspector.get_indexes(table_name)
        if item.get("name")
    }


def _add_station_fee() -> None:
    station_columns = _columns("stations")
    station_constraints = _constraint_names("stations")
    with op.batch_alter_table("stations") as batch:
        if "no_show_fee_vnd" not in station_columns:
            batch.add_column(
                sa.Column(
                    "no_show_fee_vnd",
                    sa.Integer(),
                    nullable=False,
                    server_default="0",
                )
            )
        if "ck_stations_no_show_fee_nonneg" not in station_constraints:
            batch.create_check_constraint(
                "ck_stations_no_show_fee_nonneg", "no_show_fee_vnd >= 0"
            )


def _add_s52_state_to_s48_table() -> None:
    columns = _columns("reservations")
    constraints = _constraint_names("reservations")
    with op.batch_alter_table("reservations") as batch:
        additions = (
            sa.Column("connector_db_id", sa.Integer(), nullable=True),
            sa.Column("id_tag_id", sa.Integer(), nullable=True),
            sa.Column("fulfilled_session_id", sa.Integer(), nullable=True),
            sa.Column("fulfilled_at", sa.DateTime(), nullable=True),
            sa.Column("expired_at", sa.DateTime(), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("no_show_fee_vnd", sa.Integer(), nullable=True),
            sa.Column("fee_ledger_entry_id", sa.Integer(), nullable=True),
            sa.Column("fee_waived_reason", sa.String(length=200), nullable=True),
            sa.Column(
                "cancel_status",
                sa.String(length=20),
                nullable=False,
                server_default="not_needed",
            ),
            sa.Column(
                "cancel_attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("last_cancel_attempt_at", sa.DateTime(), nullable=True),
        )
        for column in additions:
            if column.name not in columns:
                batch.add_column(column)

        if "fk_reservations_connector_db_id_connectors" not in constraints:
            batch.create_foreign_key(
                "fk_reservations_connector_db_id_connectors",
                "connectors",
                ["connector_db_id"],
                ["id"],
                ondelete="RESTRICT",
            )
        if "fk_reservations_id_tag_id_id_tags" not in constraints:
            batch.create_foreign_key(
                "fk_reservations_id_tag_id_id_tags",
                "id_tags",
                ["id_tag_id"],
                ["id"],
                ondelete="RESTRICT",
            )
        if "fk_reservations_fulfilled_session_id_charging_sessions" not in constraints:
            batch.create_foreign_key(
                "fk_reservations_fulfilled_session_id_charging_sessions",
                "charging_sessions",
                ["fulfilled_session_id"],
                ["id"],
                ondelete="SET NULL",
            )

        if "ck_reservation_status" not in constraints:
            batch.create_check_constraint(
                "ck_reservation_status",
                "status IN ('pending', 'accepted', 'rejected', 'expired', 'cancelled', 'completed')",
            )
        if "ck_reservation_cancel_status" not in constraints:
            batch.create_check_constraint(
                "ck_reservation_cancel_status",
                "cancel_status IN ('not_needed', 'pending', 'done', 'gone', 'abandoned')",
            )
        if "ck_reservation_fee_nonneg" not in constraints:
            batch.create_check_constraint(
                "ck_reservation_fee_nonneg",
                "no_show_fee_vnd IS NULL OR no_show_fee_vnd >= 0",
            )
        if "ck_reservation_cancel_attempts" not in constraints:
            batch.create_check_constraint(
                "ck_reservation_cancel_attempts", "cancel_attempts >= 0"
            )

    # Preserve both identifiers: connector_id is the OCPP number, while
    # connector_db_id is the connectors table primary key used by S-52 jobs.
    op.execute(
        sa.text(
            "UPDATE reservations SET connector_db_id = ("
            "SELECT c.id FROM connectors c "
            "WHERE c.charge_point_id = reservations.charge_point_id "
            "AND c.connector_id = reservations.connector_id ORDER BY c.id LIMIT 1) "
            "WHERE connector_db_id IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE reservations SET id_tag_id = ("
            "SELECT t.id FROM id_tags t WHERE t.id_tag = reservations.id_tag "
            "ORDER BY t.id LIMIT 1) WHERE id_tag_id IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE reservations SET no_show_fee_vnd = COALESCE(("
            "SELECT s.no_show_fee_vnd FROM charge_points cp "
            "JOIN stations s ON s.id = cp.station_id "
            "WHERE cp.id = reservations.charge_point_id), 0) "
            "WHERE no_show_fee_vnd IS NULL"
        )
    )

    desired_indexes = {
        "ix_reservations_status_expiry": ["status", "expiry_date"],
        "ix_reservations_connector_status": ["connector_db_id", "status"],
        "ix_reservations_driver_status": ["user_id", "status"],
    }
    indexes = _index_columns("reservations")
    for name, columns in desired_indexes.items():
        if name in indexes and indexes[name] != columns:
            op.drop_index(name, table_name="reservations")
            indexes.pop(name)
        if name not in indexes:
            op.create_index(name, "reservations", columns)


def _update_wallet_constraint() -> None:
    constraints = _constraint_names("wallet_ledger")
    if "ck_wallet_ledger_amount_sign" in constraints:
        with op.batch_alter_table("wallet_ledger") as batch:
            batch.drop_constraint("ck_wallet_ledger_amount_sign", type_="check")
            batch.create_check_constraint(
                "ck_wallet_ledger_amount_sign", _LEDGER_CHECK
            )


def upgrade() -> None:
    _add_station_fee()

    reservation_columns = _columns("reservations")
    if "charge_point_id" in reservation_columns:
        # The integrated S-48 table already exists; extend it rather than
        # creating a second, incompatible reservations table.
        _add_s52_state_to_s48_table()
    elif reservation_columns:
        # A database created from the standalone S-52 branch already has its
        # legacy reservation shape. The integration migration converts it.
        pass
    else:
        raise RuntimeError(
            "S-48 migration must create reservations before S-52 can extend it"
        )

    _update_wallet_constraint()


def downgrade() -> None:
    bind = op.get_bind()
    has_no_show = bind.execute(
        sa.text("SELECT 1 FROM wallet_ledger WHERE entry_type = 'no_show_fee' LIMIT 1")
    ).first()
    if has_no_show:
        raise RuntimeError(
            "Có bút toán no_show_fee trong sổ cái; "
            "cần forward migration để xoá dữ liệu trước khi downgrade"
        )

    columns = _columns("reservations")
    if "charge_point_id" in columns:
        indexes = _index_columns("reservations")
        for name in (
            "ix_reservations_driver_status",
            "ix_reservations_connector_status",
            "ix_reservations_status_expiry",
        ):
            if name in indexes:
                op.drop_index(name, table_name="reservations")

        constraints = _constraint_names("reservations")
        with op.batch_alter_table("reservations") as batch:
            for name in (
                "ck_reservation_cancel_attempts",
                "ck_reservation_fee_nonneg",
                "ck_reservation_cancel_status",
                "ck_reservation_status",
            ):
                if name in constraints:
                    batch.drop_constraint(name, type_="check")
            for name in (
                "fk_reservations_fulfilled_session_id_charging_sessions",
                "fk_reservations_id_tag_id_id_tags",
                "fk_reservations_connector_db_id_connectors",
            ):
                if name in constraints:
                    batch.drop_constraint(name, type_="foreignkey")
            for name in (
                "last_cancel_attempt_at",
                "cancel_attempts",
                "cancel_status",
                "fee_waived_reason",
                "fee_ledger_entry_id",
                "no_show_fee_vnd",
                "cancelled_at",
                "expired_at",
                "fulfilled_at",
                "fulfilled_session_id",
                "id_tag_id",
                "connector_db_id",
            ):
                if name in columns:
                    batch.drop_column(name)

    station_columns = _columns("stations")
    if "no_show_fee_vnd" in station_columns:
        station_constraints = _constraint_names("stations")
        with op.batch_alter_table("stations") as batch:
            if "ck_stations_no_show_fee_nonneg" in station_constraints:
                batch.drop_constraint(
                    "ck_stations_no_show_fee_nonneg", type_="check"
                )
            batch.drop_column("no_show_fee_vnd")

    _update_wallet_constraint()
