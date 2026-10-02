"""
Migration: tao bang users, roles, user_roles va seed 5 vai tro
Tham chieu: SPRINT_1.md T-04
"""

import sqlalchemy as sa

from alembic import op

revision = "0001_create_users_roles"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Bang roles -------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # -- Bang users -------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("last_failed_ip", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    # -- Bang noi user_roles -----------------------------------------------
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )

    # -- Seed 5 vai tro (T-04 AC: phai co dung 5 dong trong roles) --------
    roles_table = sa.table("roles", sa.column("name", sa.String))
    op.bulk_insert(
        roles_table,
        [
            {"name": "driver"},
            {"name": "station_owner"},
            {"name": "operator"},
            {"name": "accountant"},
            {"name": "admin"},
        ],
    )


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
