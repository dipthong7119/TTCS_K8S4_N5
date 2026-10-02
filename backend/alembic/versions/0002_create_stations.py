"""
Migration: tao bang stations co khoa ngoai toi users
Tham chieu: SPRINT_1.md T-08
"""

import sqlalchemy as sa

from alembic import op

revision = "0002_create_stations"
down_revision = "0001_create_users_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        # active | inactive | maintenance
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # Chi muc tren owner_id -- moi truy van cua chu tram loc theo cot nay (T-08 NFR)
    op.create_index("ix_stations_owner_id", "stations", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_stations_owner_id", table_name="stations")
    op.drop_table("stations")
