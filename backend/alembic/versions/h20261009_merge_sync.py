"""merge configuration tariff and payment migrations

Revision ID: h20261009_merge_sync
Revises: h20261009_charge_point_configuration, h20261009_invoice_rounding, h20261009_payment_transactions
Create Date: 2026-10-09 20:26:20.796518

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'h20261009_merge_sync'
down_revision: tuple[str, ...] = (
    'h20261009_charge_point_configuration',
    'h20261009_invoice_rounding',
    'h20261009_payment_transactions',
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
