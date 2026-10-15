"""Track sandbox top-up refunds and allow their wallet reversal entry."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261013_payment_refunds"
down_revision: str | None = "h20261011_remote_start"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payment_transactions",
        sa.Column("refund_reason", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "payment_transactions",
        sa.Column("refunded_at", sa.DateTime(), nullable=True),
    )
    with op.batch_alter_table("wallet_ledger") as batch:
        batch.drop_constraint("ck_wallet_ledger_amount_sign", type_="check")
        batch.create_check_constraint(
            "ck_wallet_ledger_amount_sign",
            "(entry_type IN ('manual_topup', 'demo_topup', 'sandbox_topup', 'refund') AND amount_vnd > 0) OR "
            "(entry_type IN ('session_charge', 'subscription_charge', 'payment_refund') AND amount_vnd < 0)",
        )


def downgrade() -> None:
    bind = op.get_bind()
    has_refunded_transactions = bind.execute(
        sa.text("SELECT 1 FROM payment_transactions WHERE status = 'refunded' LIMIT 1")
    ).first()
    has_payment_refunds = bind.execute(
        sa.text("SELECT 1 FROM wallet_ledger WHERE entry_type = 'payment_refund' LIMIT 1")
    ).first()
    if has_refunded_transactions or has_payment_refunds:
        raise RuntimeError(
            "Sandbox top-up refunds exist; preserve them with a forward migration"
        )

    with op.batch_alter_table("wallet_ledger") as batch:
        batch.drop_constraint("ck_wallet_ledger_amount_sign", type_="check")
        batch.create_check_constraint(
            "ck_wallet_ledger_amount_sign",
            "(entry_type IN ('manual_topup', 'demo_topup', 'sandbox_topup', 'refund') AND amount_vnd > 0) OR "
            "(entry_type IN ('session_charge', 'subscription_charge') AND amount_vnd < 0)",
        )
    op.drop_column("payment_transactions", "refunded_at")
    op.drop_column("payment_transactions", "refund_reason")
