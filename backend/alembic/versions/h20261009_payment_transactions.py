"""create payment_transactions for sandbox wallet topups

Revision ID: h20261009_payment_transactions
Revises: h20261007_needs_review
Create Date: 2026-10-09 16:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'h20261009_payment_transactions'
down_revision: str | None = 'h20261007_needs_review'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_code", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("amount_vnd", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="pending", nullable=False
        ),
        sa.Column(
            "provider", sa.String(length=30), server_default="sandbox", nullable=False
        ),
        sa.Column("payment_url", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("order_code", name="uq_payment_transactions_order_code"),
    )
    op.create_index(
        "ix_payment_transactions_order_code", "payment_transactions", ["order_code"]
    )
    op.create_index(
        "ix_payment_transactions_user_id", "payment_transactions", ["user_id"]
    )
    op.create_index(
        "ix_payment_transactions_user_status",
        "payment_transactions",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_payment_transactions_created", "payment_transactions", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payment_transactions_created", table_name="payment_transactions"
    )
    op.drop_index(
        "ix_payment_transactions_user_status", table_name="payment_transactions"
    )
    op.drop_index(
        "ix_payment_transactions_user_id", table_name="payment_transactions"
    )
    op.drop_index(
        "ix_payment_transactions_order_code", table_name="payment_transactions"
    )
    op.drop_table("payment_transactions")
