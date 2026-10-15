"""SCRUM-68: monthly plans, driver subscriptions, invoices, and owner usage shares."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261010_monthly_subscriptions"
down_revision: str | None = "e97a880b36e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("monthly_fee_vnd", sa.Integer(), nullable=False),
        sa.Column("price_vnd_per_kwh", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("monthly_fee_vnd > 0", name="ck_subscription_plan_fee_positive"),
        sa.CheckConstraint(
            "price_vnd_per_kwh >= 0", name="ck_subscription_plan_rate_nonnegative"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        "ix_subscription_plans_active_name", "subscription_plans", ["is_active", "name"]
    )

    op.create_table(
        "driver_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("plan_name", sa.String(length=120), nullable=False),
        sa.Column("monthly_fee_vnd", sa.Integer(), nullable=False),
        sa.Column("price_vnd_per_kwh", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "monthly_fee_vnd > 0", name="ck_driver_subscription_fee_positive"
        ),
        sa.CheckConstraint(
            "price_vnd_per_kwh >= 0", name="ck_driver_subscription_rate_nonnegative"
        ),
        sa.CheckConstraint(
            "expires_at > starts_at", name="ck_driver_subscription_period_valid"
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_driver_subscriptions_user_period",
        "driver_subscriptions",
        ["user_id", "starts_at", "expires_at"],
    )

    op.create_table(
        "subscription_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("charging_session_id", sa.Integer(), nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("station_owner_id", sa.Integer(), nullable=False),
        sa.Column("energy_wh", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "energy_wh >= 0", name="ck_subscription_usage_energy_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["charging_session_id"], ["charging_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["station_id"], ["stations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["station_owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["driver_subscriptions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("charging_session_id", name="uq_subscription_usage_session"),
    )
    op.create_index(
        "ix_subscription_usage_subscription_owner",
        "subscription_usage",
        ["subscription_id", "station_owner_id"],
    )

    with op.batch_alter_table("wallet_ledger") as batch:
        batch.drop_constraint("ck_wallet_ledger_amount_sign", type_="check")
        batch.create_check_constraint(
            "ck_wallet_ledger_amount_sign",
            "(entry_type IN ('manual_topup', 'demo_topup', 'sandbox_topup', 'refund') AND amount_vnd > 0) OR "
            "(entry_type IN ('session_charge', 'subscription_charge') AND amount_vnd < 0)",
        )

    with op.batch_alter_table("charging_invoices") as batch:
        batch.alter_column(
            "tariff_id", existing_type=sa.Integer(), nullable=True
        )
        batch.add_column(sa.Column("subscription_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("package_name", sa.String(length=120), nullable=True))
        batch.create_foreign_key(
            "fk_charging_invoices_subscription",
            "driver_subscriptions",
            ["subscription_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_check_constraint(
            "ck_charging_invoice_has_pricing_source",
            "tariff_id IS NOT NULL OR subscription_id IS NOT NULL",
        )
        batch.create_index("ix_charging_invoices_subscription", ["subscription_id"])


def downgrade() -> None:
    bind = op.get_bind()
    has_subscription_invoices = bind.execute(
        sa.text("SELECT 1 FROM charging_invoices WHERE subscription_id IS NOT NULL LIMIT 1")
    ).first()
    has_subscription_data = bind.execute(
        sa.text("SELECT 1 FROM driver_subscriptions LIMIT 1")
    ).first()
    has_subscription_charges = bind.execute(
        sa.text("SELECT 1 FROM wallet_ledger WHERE entry_type = 'subscription_charge' LIMIT 1")
    ).first()
    if has_subscription_invoices or has_subscription_data or has_subscription_charges:
        raise RuntimeError(
            "SCRUM-68 data exists; create a forward migration instead of downgrading it"
        )

    with op.batch_alter_table("charging_invoices") as batch:
        batch.drop_index("ix_charging_invoices_subscription")
        batch.drop_constraint("ck_charging_invoice_has_pricing_source", type_="check")
        batch.drop_constraint("fk_charging_invoices_subscription", type_="foreignkey")
        batch.drop_column("package_name")
        batch.drop_column("subscription_id")
        batch.alter_column(
            "tariff_id", existing_type=sa.Integer(), nullable=False
        )

    with op.batch_alter_table("wallet_ledger") as batch:
        batch.drop_constraint("ck_wallet_ledger_amount_sign", type_="check")
        batch.create_check_constraint(
            "ck_wallet_ledger_amount_sign",
            "(entry_type IN ('manual_topup', 'demo_topup', 'sandbox_topup', 'refund') AND amount_vnd > 0) OR "
            "(entry_type = 'session_charge' AND amount_vnd < 0)",
        )

    op.drop_index("ix_subscription_usage_subscription_owner", table_name="subscription_usage")
    op.drop_table("subscription_usage")
    op.drop_index("ix_driver_subscriptions_user_period", table_name="driver_subscriptions")
    op.drop_table("driver_subscriptions")
    op.drop_index("ix_subscription_plans_active_name", table_name="subscription_plans")
    op.drop_table("subscription_plans")
