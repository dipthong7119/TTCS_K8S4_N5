"""Reconcile demo schema changes that were added to an applied revision."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f39e27b14c02"
down_revision: str | None = "e81f0a6b2c44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # Some development databases already stamped e81f0a6b2c44 before these
    # columns/tables were added to that revision. Add only the missing pieces.
    column_additions = {
        "charging_sessions": {
            "remote_stop_requested_at": sa.Column(
                "remote_stop_requested_at", sa.DateTime()
            ),
        },
        "audit_logs": {
            "actor_email": sa.Column("actor_email", sa.String(255)),
            "actor_name": sa.Column("actor_name", sa.String(255)),
        },
    }
    for table_name, columns in column_additions.items():
        if table_name not in tables:
            continue
        existing_columns = {
            column["name"] for column in inspector.get_columns(table_name)
        }
        for column_name, column in columns.items():
            if column_name not in existing_columns:
                op.add_column(table_name, column)

    if "meter_values" not in tables:
        op.create_table(
            "meter_values",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("measured_at", sa.DateTime(), nullable=False),
            sa.Column("measurand", sa.String(80), nullable=False),
            sa.Column("value", sa.Numeric(18, 6), nullable=False),
            sa.Column("unit", sa.String(20), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["session_id"], ["charging_sessions.id"], ondelete="CASCADE"
            ),
        )

    if "orphan_messages" not in tables:
        op.create_table(
            "orphan_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("charge_point_code", sa.String(50), nullable=False),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("transaction_id", sa.Integer(), nullable=True),
            sa.Column("connector_number", sa.Integer(), nullable=True),
            sa.Column("reason", sa.String(80), nullable=False),
            sa.Column(
                "payload", sa.JSON(), server_default=sa.text("'{}'"), nullable=False
            ),
            sa.Column(
                "received_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )

    inspector = sa.inspect(bind)
    index_additions = {
        "meter_values": {
            "ix_meter_values_session_measured": ["session_id", "measured_at"],
        },
        "orphan_messages": {
            "ix_orphan_messages_cp_received": ["charge_point_code", "received_at"],
            "ix_orphan_messages_transaction": ["transaction_id", "received_at"],
        },
    }
    for table_name, indexes in index_additions.items():
        existing_indexes = {
            index["name"] for index in inspector.get_indexes(table_name)
        }
        for index_name, columns in indexes.items():
            if index_name not in existing_indexes:
                op.create_index(index_name, table_name, columns)


def downgrade() -> None:
    # This revision repairs schemas where the previous revision was already
    # applied; dropping these columns/tables could discard live application data.
    pass
