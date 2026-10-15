"""merge audit target user and payment refunds heads

Revision ID: 4591d08fb87f
Revises: h20261013_audit_target_user, h20261013_payment_refunds
Create Date: 2026-10-15 18:54:32.359970

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4591d08fb87f"
down_revision: str | None = ("h20261013_audit_target_user", "h20261013_payment_refunds")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("wallet_ledger") as batch:
        batch.drop_constraint("ck_wallet_ledger_amount_sign", type_="check")
        batch.create_check_constraint(
            "ck_wallet_ledger_amount_sign",
            "(entry_type IN ('manual_topup', 'demo_topup', 'sandbox_topup', 'refund') AND amount_vnd > 0) OR "
            "(entry_type IN ('session_charge', 'subscription_charge', 'payment_refund') AND amount_vnd < 0) OR "
            "(entry_type = 'adjustment' AND amount_vnd != 0)",
        )


def downgrade() -> None:
    pass
