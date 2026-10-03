"""Store the original CALL frame with its persisted response.

Revision ID: h20261003_t21_ocpp_request_payload
Revises: df03d362bc53
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261003_t21_ocpp_request_payload"
down_revision: str | None = "df03d362bc53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("ocpp_messages")
    }
    if "request_payload" not in columns:
        op.add_column(
            "ocpp_messages",
            sa.Column("request_payload", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("ocpp_messages")
    }
    if "request_payload" in columns:
        op.drop_column("ocpp_messages", "request_payload")
