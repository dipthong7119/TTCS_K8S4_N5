"""Store failed-login counters by client IP without synthetic user rows."""

import sqlalchemy as sa

from alembic import op

revision = "9f2c6a1b7d40"
down_revision = "578e5d2ba886"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_ip_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("ip_address", name="uq_login_ip_attempts_ip_address"),
    )


def downgrade() -> None:
    op.drop_table("login_ip_attempts")
