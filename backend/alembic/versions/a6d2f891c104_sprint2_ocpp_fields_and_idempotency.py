"""Add OCPP raw status, scoped idempotency, and error lookup indexes."""

import logging
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

logger = logging.getLogger(__name__)

revision: str = "a6d2f891c104"
down_revision: str | None = "b37ad56c90e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    connector_columns = {
        column["name"] for column in inspector.get_columns("connectors")
    }
    if "ocpp_status" not in connector_columns:
        op.add_column(
            "connectors", sa.Column("ocpp_status", sa.String(50), nullable=True)
        )

    charge_point_columns = {
        column["name"] for column in inspector.get_columns("charge_points")
    }
    if "ocpp_status" not in charge_point_columns:
        op.add_column(
            "charge_points", sa.Column("ocpp_status", sa.String(50), nullable=True)
        )

    message_columns = {
        column["name"] for column in inspector.get_columns("ocpp_messages")
    }
    if "request_hash" not in message_columns:
        op.add_column(
            "ocpp_messages",
            sa.Column("request_hash", sa.String(64), nullable=False, server_default=""),
        )

    indexes = {index["name"]: index for index in inspector.get_indexes("ocpp_messages")}
    if "ix_ocpp_messages_msg_id" in indexes:
        op.drop_index("ix_ocpp_messages_msg_id", table_name="ocpp_messages")
    if "uq_ocpp_message_per_charge_point" not in indexes:
        op.create_index(
            "uq_ocpp_message_per_charge_point",
            "ocpp_messages",
            ["charge_point_code", "msg_id"],
            unique=True,
        )

    error_indexes = {
        index["name"] for index in inspector.get_indexes("connector_errors")
    }
    if "ix_connector_errors_connector_timestamp" not in error_indexes:
        op.create_index(
            "ix_connector_errors_connector_timestamp",
            "connector_errors",
            ["connector_id", "timestamp"],
        )


def downgrade() -> None:
    try:
        op.drop_index(
            "ix_connector_errors_connector_timestamp", table_name="connector_errors"
        )
    except Exception as e:
        logger.warning("Drop index failed: %s", e)
    op.drop_index("uq_ocpp_message_per_charge_point", table_name="ocpp_messages")
    try:
        op.create_index(
            "ix_ocpp_messages_msg_id", "ocpp_messages", ["msg_id"], unique=True
        )
    except Exception as e:
        logger.warning("Create index failed: %s", e)
    with op.batch_alter_table("ocpp_messages") as batch_op:
        batch_op.drop_column("request_hash")
    with op.batch_alter_table("connectors") as batch_op:
        batch_op.drop_column("ocpp_status")
    with op.batch_alter_table("charge_points") as batch_op:
        batch_op.drop_column("ocpp_status")
