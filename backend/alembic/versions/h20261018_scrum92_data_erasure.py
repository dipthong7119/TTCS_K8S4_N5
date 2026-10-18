"""SCRUM-92 / S-57: Create data_erasure_requests table and unify heads.

Revision ID: h20261018_scrum92_data_erasure
Revises: h20261016_integrate_feature_heads, 4591d08fb87f
Create Date: 2026-10-18 15:16:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h20261018_scrum92_data_erasure"
down_revision: tuple[str, str] = (
    "h20261016_integrate_feature_heads",
    "4591d08fb87f",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("data_erasure_requests"):
        op.create_table(
            "data_erasure_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="pending",
            ),
            sa.Column("request_reason", sa.String(length=500), nullable=True),
            sa.Column("rejection_reason", sa.String(length=500), nullable=True),
            sa.Column(
                "requested_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.Column(
                "processed_by",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'approved', 'rejected')",
                name="ck_data_erasure_requests_status",
            ),
        )
        op.create_index(
            "ix_data_erasure_requests_user_id",
            "data_erasure_requests",
            ["user_id"],
        )
        op.create_index(
            "ix_data_erasure_requests_user_status",
            "data_erasure_requests",
            ["user_id", "status"],
        )


def downgrade() -> None:
    raise RuntimeError(
        "Migration SCRUM-92 không hỗ trợ downgrade tự động; "
        "cần forward migration để xử lý dữ liệu trước khi rollback"
    )
