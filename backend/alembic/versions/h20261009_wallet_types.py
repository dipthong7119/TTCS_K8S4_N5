"""SCRUM-69: align migrated wallet constraints with sandbox topups and refunds."""

from collections.abc import Sequence

from alembic import op

revision: str = "h20261009_wallet_types"
down_revision: str | None = "h20261009_merge_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("wallet_ledger") as batch:
        batch.drop_constraint("ck_wallet_ledger_amount_sign", type_="check")
        batch.create_check_constraint(
            "ck_wallet_ledger_amount_sign",
            "(entry_type IN ('manual_topup', 'demo_topup', 'sandbox_topup', 'refund') AND amount_vnd > 0) OR "
            "(entry_type = 'session_charge' AND amount_vnd < 0)",
        )


def downgrade() -> None:
    with op.batch_alter_table("wallet_ledger") as batch:
        batch.drop_constraint("ck_wallet_ledger_amount_sign", type_="check")
        batch.create_check_constraint(
            "ck_wallet_ledger_amount_sign",
            "(entry_type IN ('manual_topup', 'demo_topup') AND amount_vnd > 0) OR "
            "(entry_type = 'session_charge' AND amount_vnd < 0)",
        )
