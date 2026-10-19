"""Ensure the privacy request schema exists on databases already at the current head.

Revision ID: privacy_schema_reconcile_v1
Revises: h20261021_scrum87_reconciliation_period_locks
Create Date: 2026-10-19 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "privacy_schema_reconcile_v1"
down_revision: str | None = "h20261021_scrum87_reconciliation_period_locks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLE = "data_erasure_requests"
STATUS_CONSTRAINT = "ck_data_erasure_requests_status"
STATUS_EXPRESSION = "status IN ('pending', 'approved', 'rejected', 'cancelled')"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "status", sa.String(20), nullable=False, server_default="pending"
            ),
            sa.Column("request_reason", sa.String(500), nullable=True),
            sa.Column("request_reason_label", sa.String(255), nullable=True),
            sa.Column("request_reason_detail", sa.String(2000), nullable=True),
            sa.Column("rejection_reason", sa.String(500), nullable=True),
            sa.Column(
                "requested_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column(
                "processed_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint(STATUS_EXPRESSION, name=STATUS_CONSTRAINT),
        )
        inspector = sa.inspect(bind)

    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    if "request_reason_label" not in columns:
        op.add_column(TABLE, sa.Column("request_reason_label", sa.String(255)))
    if "request_reason_detail" not in columns:
        op.add_column(TABLE, sa.Column("request_reason_detail", sa.String(2000)))

    indexes = {index["name"] for index in inspector.get_indexes(TABLE)}
    if "ix_data_erasure_requests_user_id" not in indexes:
        op.create_index(
            "ix_data_erasure_requests_user_id", TABLE, ["user_id"], unique=False
        )
    if "ix_data_erasure_requests_user_status" not in indexes:
        op.create_index(
            "ix_data_erasure_requests_user_status",
            TABLE,
            ["user_id", "status"],
            unique=False,
        )

    checks = inspector.get_check_constraints(TABLE)
    status_check = next(
        (
            check
            for check in checks
            if "status" in (check.get("sqltext") or "").lower()
        ),
        None,
    )
    status_expression = (
        (status_check.get("sqltext") or "").lower() if status_check else ""
    )
    if status_check is None or "cancelled" not in status_expression:
        with op.batch_alter_table(TABLE) as batch_op:
            if status_check and status_check.get("name"):
                batch_op.drop_constraint(status_check["name"], type_="check")
            batch_op.create_check_constraint(STATUS_CONSTRAINT, STATUS_EXPRESSION)


def downgrade() -> None:
    # This is a schema repair for data that may already exist. Keep the repaired table.
    pass
