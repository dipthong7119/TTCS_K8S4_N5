"""Allow reopening SCRUM-87 periods while preserving every closed snapshot.

Revision ID: h20261022_scrum87_reopen_period
Revises: privacy_schema_reconcile_v1
Create Date: 2026-10-22 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261022_scrum87_reopen_period"
down_revision: str | None = "privacy_schema_reconcile_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reconciliation_period_locks") as batch_op:
        batch_op.drop_constraint("ck_recon_lock_status_locked", type_="check")
        batch_op.create_check_constraint(
            "ck_recon_lock_status", "status IN ('locked', 'reopened')"
        )

    op.create_table(
        "reconciliation_period_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "period_lock_id",
            sa.Integer(),
            sa.ForeignKey("reconciliation_period_locks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "locked_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("locked_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("revision > 0", name="ck_recon_period_snapshot_revision"),
        sa.UniqueConstraint(
            "period_lock_id", "revision", name="uq_recon_period_snapshot_revision"
        ),
    )

    period_locks = sa.table(
        "reconciliation_period_locks",
        sa.column("id", sa.Integer()),
        sa.column("snapshot", sa.JSON()),
        sa.column("locked_by_id", sa.Integer()),
        sa.column("locked_at", sa.DateTime()),
    )
    snapshots = sa.table(
        "reconciliation_period_snapshots",
        sa.column("period_lock_id", sa.Integer()),
        sa.column("revision", sa.Integer()),
        sa.column("snapshot", sa.JSON()),
        sa.column("locked_by_id", sa.Integer()),
        sa.column("locked_at", sa.DateTime()),
    )
    op.execute(
        snapshots.insert().from_select(
            ["period_lock_id", "revision", "snapshot", "locked_by_id", "locked_at"],
            sa.select(
                period_locks.c.id,
                sa.literal(1),
                period_locks.c.snapshot,
                period_locks.c.locked_by_id,
                period_locks.c.locked_at,
            ),
        )
    )


def downgrade() -> None:
    op.drop_table("reconciliation_period_snapshots")
    with op.batch_alter_table("reconciliation_period_locks") as batch_op:
        batch_op.drop_constraint("ck_recon_lock_status", type_="check")
        batch_op.create_check_constraint("ck_recon_lock_status_locked", "status = 'locked'")
