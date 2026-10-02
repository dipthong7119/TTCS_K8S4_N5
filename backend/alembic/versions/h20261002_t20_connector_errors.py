"""SCRUM-120: Schema chuẩn cho connector_errors

Revision ID: h20261002_t20_connector_errors
Revises: h20261002_t19_status
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "h20261002_t20_connector_errors"
down_revision: str | None = "h20261002_t19_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {idx["name"] for idx in inspector.get_indexes("connector_errors")}
    if "ix_connector_errors_connector_timestamp" in indexes:
        op.drop_index("ix_connector_errors_connector_timestamp", table_name="connector_errors")

    columns = {col["name"] for col in inspector.get_columns("connector_errors")}

    with op.batch_alter_table("connector_errors", schema=None) as batch_op:
        if "occurred_at" not in columns:
            batch_op.add_column(sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
        if "info" in columns:
            batch_op.drop_column("info")
        if "timestamp" in columns:
            batch_op.drop_column("timestamp")
        if "updated_at" in columns:
            batch_op.drop_column("updated_at")

    if "ix_connector_errors_connector_occurred" not in indexes:
        op.create_index("ix_connector_errors_connector_occurred", "connector_errors", ["connector_id", "occurred_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {idx["name"] for idx in inspector.get_indexes("connector_errors")}
    if "ix_connector_errors_connector_occurred" in indexes:
        op.drop_index("ix_connector_errors_connector_occurred", table_name="connector_errors")

    columns = {col["name"] for col in inspector.get_columns("connector_errors")}

    with op.batch_alter_table("connector_errors", schema=None) as batch_op:
        if "info" not in columns:
            batch_op.add_column(sa.Column("info", sa.String(length=500), nullable=True))
        if "timestamp" not in columns:
            batch_op.add_column(sa.Column("timestamp", sa.DateTime(), nullable=True))
        if "updated_at" not in columns:
            batch_op.add_column(sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False))
        if "occurred_at" in columns:
            batch_op.drop_column("occurred_at")

    if "ix_connector_errors_connector_timestamp" not in indexes:
        try:
            op.create_index("ix_connector_errors_connector_timestamp", "connector_errors", ["connector_id", "timestamp"])
        except Exception:
            pass
