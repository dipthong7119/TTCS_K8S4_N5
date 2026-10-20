"""Persist privacy page details and allow driver cancellation.

Revision ID: h20261018_privacy_page_compat
Revises: h20261018_scrum92_data_erasure
Create Date: 2026-10-18 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261018_privacy_page_compat"
down_revision: str | None = "h20261018_scrum92_data_erasure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("data_erasure_requests") as batch_op:
        batch_op.add_column(
            sa.Column("request_reason_label", sa.String(255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("request_reason_detail", sa.String(2000), nullable=True)
        )
        batch_op.drop_constraint(
            "ck_data_erasure_requests_status", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_data_erasure_requests_status",
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
        )


def downgrade() -> None:
    with op.batch_alter_table("data_erasure_requests") as batch_op:
        batch_op.drop_constraint(
            "ck_data_erasure_requests_status", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_data_erasure_requests_status",
            "status IN ('pending', 'approved', 'rejected')",
        )
        batch_op.drop_column("request_reason_detail")
        batch_op.drop_column("request_reason_label")
