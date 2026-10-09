"""Persist the rounding rule used for each immutable invoice."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261009_invoice_rounding"
down_revision: str | None = "h20261009_tariff_fees"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_DEFAULT_RULE = "Làm tròn HALF_UP đến đồng trên từng khung giá; phí chiếm trụ tính mỗi phút bắt đầu sau ân hạn."


def upgrade() -> None:
    op.add_column(
        "charging_invoices",
        sa.Column("rounding_rule", sa.String(length=150), server_default=_DEFAULT_RULE, nullable=False),
    )


def downgrade() -> None:
    op.drop_column("charging_invoices", "rounding_rule")
