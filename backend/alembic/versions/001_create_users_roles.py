"""create_users_roles

Revision ID: 001_create_users_roles
Revises:
Create Date: 2026-09-24

Task T-04 — Sprint 1
Tạo ba bảng: roles, users, user_roles.
Seed sẵn 5 vai trò: driver, station_owner, operator, accountant, admin.

Migration tiến và lùi được (downgrade DROP bảng theo thứ tự ngược).
"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

# Revision identifiers
revision: str = "001_create_users_roles"
down_revision = None
branch_labels = None
depends_on = None

# Seed data — 5 vai trò bắt buộc (T-04)
SEED_ROLES = [
    {"id": 1, "name": "driver"},           # Tài xế
    {"id": 2, "name": "station_owner"},    # Chủ trạm
    {"id": 3, "name": "operator"},         # Vận hành viên
    {"id": 4, "name": "accountant"},       # Kế toán
    {"id": 5, "name": "admin"},            # Quản trị
]


def upgrade() -> None:
    # ── Bảng roles ────────────────────────────────────────────────────────────
    roles_table = op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )

    # Seed 5 vai trò ngay trong migration — đảm bảo luôn có khi container khởi động
    now = datetime.now(tz=timezone.utc)
    op.bulk_insert(
        roles_table,
        [{"id": r["id"], "name": r["name"], "created_at": now} for r in SEED_ROLES],
    )

    # ── Bảng users ────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False),
        # Đủ dài cho hash argon2id (NFR T-04)
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        # Brute-force protection — lưu ở DB, không lưu biến tiến trình (SSD-1)
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failed_ip", sa.String(45), nullable=True),  # IPv4/IPv6
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
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── Bảng user_roles (nối nhiều-nhiều) ────────────────────────────────────
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_user_roles_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"],
            name="fk_user_roles_role_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name="pk_user_roles"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles"),
    )


def downgrade() -> None:
    # Xoá theo thứ tự ngược — child trước, parent sau
    op.drop_table("user_roles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
    op.drop_table("roles")
