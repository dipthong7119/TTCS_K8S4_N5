"""Add station tariffs, immutable invoices, and wallet ledger."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260928_wallet"
down_revision: str | None = "f39e27b14c02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "station_tariffs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("timezone_name", sa.String(80), nullable=False),
        sa.Column("effective_from", sa.DateTime(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["station_id"], ["stations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "station_id", "effective_from", name="uq_station_tariff_effective"
        ),
    )
    op.create_index(
        "ix_station_tariffs_station_effective",
        "station_tariffs",
        ["station_id", "effective_from"],
    )
    op.create_table(
        "tariff_bands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tariff_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.Column("end_minute", sa.Integer(), nullable=False),
        sa.Column("price_vnd_per_kwh", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tariff_id"], ["station_tariffs.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "start_minute >= 0 AND start_minute < 1440 AND "
            "end_minute > start_minute AND end_minute <= 1440",
            name="ck_tariff_band_minutes",
        ),
        sa.CheckConstraint(
            "price_vnd_per_kwh >= 0", name="ck_tariff_band_price_nonnegative"
        ),
        sa.UniqueConstraint("tariff_id", "start_minute", name="uq_tariff_band_start"),
    )
    op.create_index(
        "ix_tariff_bands_tariff_minutes",
        "tariff_bands",
        ["tariff_id", "start_minute", "end_minute"],
    )
    op.create_table(
        "charging_invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("tariff_id", sa.Integer(), nullable=False),
        sa.Column("total_vnd", sa.Integer(), nullable=False),
        sa.Column("segments", sa.JSON(), nullable=False),
        sa.Column("calculation_version", sa.String(30), nullable=False),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["charging_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["tariff_id"], ["station_tariffs.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("session_id", name="uq_charging_invoices_session"),
        sa.CheckConstraint(
            "total_vnd >= 0", name="ck_charging_invoice_total_nonnegative"
        ),
    )
    op.create_index("ix_charging_invoices_tariff", "charging_invoices", ["tariff_id"])
    op.create_table(
        "wallet_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(30), nullable=False),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("reference_type", sa.String(30), nullable=True),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column("receipt_code", sa.String(80), nullable=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "(entry_type IN ('manual_topup', 'demo_topup') AND amount_vnd > 0) OR "
            "(entry_type = 'session_charge' AND amount_vnd < 0)",
            name="ck_wallet_ledger_amount_sign",
        ),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_wallet_user_idempotency"
        ),
        sa.UniqueConstraint("receipt_code", name="uq_wallet_receipt_code"),
    )
    op.create_index(
        "ix_wallet_ledger_user_created",
        "wallet_ledger",
        ["user_id", "created_at", "id"],
    )
    op.create_index(
        "ix_wallet_ledger_reference",
        "wallet_ledger",
        ["reference_type", "reference_id"],
    )

    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for table in ("charging_invoices", "wallet_ledger"):
            for operation in ("UPDATE", "DELETE"):
                operation_name = operation.lower()
                op.execute(
                    f"CREATE TRIGGER {table}_no_{operation_name} BEFORE {operation} ON {table} "
                    f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
                )
    elif dialect == "postgresql":
        op.execute(
            "CREATE FUNCTION prevent_financial_record_mutation() RETURNS trigger AS $$ "
            "BEGIN RAISE EXCEPTION 'Financial records are append-only'; END; $$ LANGUAGE plpgsql"
        )
        for table in ("charging_invoices", "wallet_ledger"):
            op.execute(
                f"CREATE TRIGGER {table}_no_mutation BEFORE UPDATE OR DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION prevent_financial_record_mutation()"
            )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        for table in ("charging_invoices", "wallet_ledger"):
            for operation in ("update", "delete"):
                op.execute(f"DROP TRIGGER IF EXISTS {table}_no_{operation}")
    elif dialect == "postgresql":
        for table in ("charging_invoices", "wallet_ledger"):
            op.execute(f"DROP TRIGGER IF EXISTS {table}_no_mutation ON {table}")
        op.execute("DROP FUNCTION IF EXISTS prevent_financial_record_mutation()")

    op.drop_index("ix_wallet_ledger_reference", table_name="wallet_ledger")
    op.drop_index("ix_wallet_ledger_user_created", table_name="wallet_ledger")
    op.drop_table("wallet_ledger")
    op.drop_index("ix_charging_invoices_tariff", table_name="charging_invoices")
    op.drop_table("charging_invoices")
    op.drop_index("ix_tariff_bands_tariff_minutes", table_name="tariff_bands")
    op.drop_table("tariff_bands")
    op.drop_index("ix_station_tariffs_station_effective", table_name="station_tariffs")
    op.drop_table("station_tariffs")
