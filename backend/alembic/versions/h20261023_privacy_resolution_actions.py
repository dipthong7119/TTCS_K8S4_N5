"""Record whether a privacy request deleted identifiers or hid the account.

Revision ID: h20261023_privacy_resolution_actions
Revises: h20261022_scrum87_reopen_period
Create Date: 2026-10-23 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261023_privacy_resolution_actions"
down_revision: str | None = "h20261022_scrum87_reopen_period"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("data_erasure_requests") as batch_op:
        batch_op.add_column(sa.Column("resolution_action", sa.String(32), nullable=True))
        batch_op.create_check_constraint(
            "ck_data_erasure_requests_resolution_action",
            "resolution_action IS NULL OR resolution_action IN ('delete_personal_data', 'hide_account')",
        )


def downgrade() -> None:
    with op.batch_alter_table("data_erasure_requests") as batch_op:
        batch_op.drop_constraint(
            "ck_data_erasure_requests_resolution_action", type_="check"
        )
        batch_op.drop_column("resolution_action")
