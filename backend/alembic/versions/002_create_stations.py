"""create_stations

Revision ID: 002_create_stations
Revises: 001_create_users_roles
Create Date: 2026-09-24

Task T-08 — Sprint 1
Tạo bảng stations với khoá ngoại tới users (chủ sở hữu),
trạng thái hoạt động, toạ độ kiểu số thực.

NFR: chỉ mục trên owner_id vì mọi truy vấn của chủ trạm lọc theo cột này.
AC:  xoá tài khoản chủ trạm còn trạm thì bị chặn bởi khoá ngoại (RESTRICT).
"""

import sqlalchemy as sa
from alembic import op

# Revision identifiers
revision: str = "002_create_stations"
down_revision = "001_create_users_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        # Toạ độ địa lý — kiểu số thực (T-08)
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        # Trạng thái: active | inactive | maintenance
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        # Khoá ngoại chủ sở hữu — RESTRICT chặn xoá user khi còn trạm
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_stations_owner_id",
            ondelete="RESTRICT",
        ),
    )

    op.create_index("ix_stations_id", "stations", ["id"])
    # Chỉ mục bắt buộc per NFR T-08
    op.create_index("ix_stations_owner_id", "stations", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_stations_owner_id", table_name="stations")
    op.drop_index("ix_stations_id", table_name="stations")
    op.drop_table("stations")
