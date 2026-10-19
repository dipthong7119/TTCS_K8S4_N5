"""Persist locked financial reconciliation snapshots (SCRUM-87).

Revision ID: h20261021_scrum87_reconciliation_period_locks
Revises: h20261020_scrum86_revenue_share_contracts
Create Date: 2026-10-21 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261021_scrum87_reconciliation_period_locks"
down_revision: str | None = "h20261020_scrum86_revenue_share_contracts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_period_locks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "station_id",
            sa.Integer(),
            sa.ForeignKey("stations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default=sa.text("'locked'")),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "locked_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("locked_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("to_date >= from_date", name="ck_recon_lock_date_range"),
        sa.CheckConstraint("status = 'locked'", name="ck_recon_lock_status_locked"),
        sa.UniqueConstraint(
            "station_id", "from_date", "to_date", name="uq_recon_lock_station_period"
        ),
    )


def downgrade() -> None:
    op.drop_table("reconciliation_period_locks")
