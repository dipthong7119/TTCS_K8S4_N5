"""Add per-charge-point OCPP configuration storage.

Revision ID: h20261009_charge_point_configuration
Revises: h20261007_needs_review
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261009_charge_point_configuration"
down_revision: str | None = "h20261007_needs_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "charge_point_configuration",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("charge_point_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('applied', 'reboot_required')",
            name="ck_charge_point_configuration_status",
        ),
        sa.ForeignKeyConstraint(
            ["charge_point_id"], ["charge_points.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "charge_point_id", "key", name="uq_charge_point_configuration_key"
        ),
    )
def downgrade() -> None:
    op.drop_table("charge_point_configuration")
