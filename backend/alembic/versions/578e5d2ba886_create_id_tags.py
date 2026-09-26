"""create_id_tags

Revision ID: 578e5d2ba886
Revises: 3c710c686e60
Create Date: 2026-09-26 16:15:19.710301

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '578e5d2ba886'
down_revision: Union[str, None] = '3c710c686e60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table("id_tags"):
        op.create_table(
            "id_tags",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("id_tag", sa.String(50), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("is_blocked", sa.Boolean(), server_default="0", nullable=False),
            sa.Column("expiry_date", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_id_tags_id_tag", "id_tags", ["id_tag"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_id_tags_id_tag", table_name="id_tags")
    op.drop_table("id_tags")
