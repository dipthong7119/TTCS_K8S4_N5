"""create_connector_errors

Revision ID: 8b30b78eea0a
Revises: 0004_seed_demo_users
Create Date: 2026-09-26 15:24:42.828137

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8b30b78eea0a'
down_revision: str | None = '0004_seed_demo_users'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table("connector_errors"):
        op.create_table(
            "connector_errors",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("connector_id", sa.Integer(), sa.ForeignKey("connectors.id", ondelete="CASCADE"), nullable=False),
            sa.Column("error_code", sa.String(50), nullable=False),
            sa.Column("vendor_error_code", sa.String(50), nullable=True),
            sa.Column("info", sa.String(500), nullable=True),
            sa.Column("timestamp", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )

def downgrade() -> None:
    op.drop_table("connector_errors")
