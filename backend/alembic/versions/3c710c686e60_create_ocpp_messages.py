"""create_ocpp_messages

Revision ID: 3c710c686e60
Revises: 8b30b78eea0a
Create Date: 2026-09-26 16:11:46.968719

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3c710c686e60'
down_revision: str | None = '8b30b78eea0a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table("ocpp_messages"):
        op.create_table(
            "ocpp_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("msg_id", sa.String(50), nullable=False),
            sa.Column("charge_point_code", sa.String(50), nullable=False),
            sa.Column("action", sa.String(50), nullable=False),
            sa.Column("response_payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_ocpp_messages_msg_id", "ocpp_messages", ["msg_id"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_ocpp_messages_msg_id", table_name="ocpp_messages")
    op.drop_table("ocpp_messages")
