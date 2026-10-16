"""SCRUM-91 / S-56: Add target_user_id to audit_logs and allow wallet adjustments."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261013_audit_target_user"
down_revision: str = "h20261013_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Thêm target_user_id vào audit_logs
    with op.batch_alter_table("audit_logs") as batch:
        batch.add_column(sa.Column("target_user_id", sa.Integer(), nullable=True))
        batch.create_index(
            "ix_audit_logs_target_created", ["target_user_id", "created_at"]
        )

    # 2. Cập nhật check constraint cho wallet_ledger để cho phép entry_type='adjustment'
    with op.batch_alter_table("wallet_ledger") as batch:
        batch.drop_constraint("ck_wallet_ledger_amount_sign", type_="check")
        batch.create_check_constraint(
            "ck_wallet_ledger_amount_sign",
            "(entry_type IN ('manual_topup', 'demo_topup', 'sandbox_topup', 'refund') AND amount_vnd > 0) OR "
            "(entry_type IN ('session_charge', 'subscription_charge') AND amount_vnd < 0) OR "
            "(entry_type = 'adjustment' AND amount_vnd != 0)",
        )


def downgrade() -> None:
    with op.batch_alter_table("wallet_ledger") as batch:
        batch.drop_constraint("ck_wallet_ledger_amount_sign", type_="check")
        batch.create_check_constraint(
            "ck_wallet_ledger_amount_sign",
            "(entry_type IN ('manual_topup', 'demo_topup', 'sandbox_topup', 'refund') AND amount_vnd > 0) OR "
            "(entry_type IN ('session_charge', 'subscription_charge') AND amount_vnd < 0)",
        )

    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_index("ix_audit_logs_target_created")
        batch.drop_column("target_user_id")
