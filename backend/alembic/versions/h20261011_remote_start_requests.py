"""S-24 / T-51: virtual driver cards and remote-start request tracking."""

import secrets
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261011_remote_start"
down_revision: str = "h20261011_merge_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "id_tags",
        sa.Column("is_virtual", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index(
        "uq_virtual_id_tag_per_user",
        "id_tags",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("is_virtual = 1"),
        postgresql_where=sa.text("is_virtual"),
    )

    op.create_table(
        "remote_start_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("driver_user_id", sa.Integer(), nullable=False),
        sa.Column("connector_id", sa.Integer(), nullable=False),
        sa.Column("id_tag_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("session_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.String(length=80), nullable=True),
        sa.CheckConstraint(
            "status IN ('sending', 'waiting_start', 'started', 'rejected', "
            "'no_reply', 'charger_error', 'expired', 'superseded')",
            name="ck_remote_start_request_status",
        ),
        sa.ForeignKeyConstraint(["driver_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["id_tag_id"], ["id_tags.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["charging_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_remote_start_active_connector",
        "remote_start_requests",
        ["connector_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('sending', 'waiting_start')"),
        postgresql_where=sa.text("status IN ('sending', 'waiting_start')"),
    )
    op.create_index(
        "ix_remote_start_driver_created",
        "remote_start_requests",
        ["driver_user_id", "created_at"],
    )
    op.create_index(
        "ix_remote_start_connector_created",
        "remote_start_requests",
        ["connector_id", "created_at"],
    )

    connection = op.get_bind()
    driver_ids = list(connection.execute(
        sa.text(
            "SELECT DISTINCT users.id FROM users "
            "JOIN user_roles ON user_roles.user_id = users.id "
            "JOIN roles ON roles.id = user_roles.role_id "
            "WHERE roles.name = 'driver' ORDER BY users.id"
        )
    ).scalars())
    id_tags = sa.table(
        "id_tags",
        sa.column("id_tag", sa.String(50)),
        sa.column("user_id", sa.Integer()),
        sa.column("is_virtual", sa.Boolean()),
        sa.column("is_blocked", sa.Boolean()),
        sa.column("expiry_date", sa.DateTime()),
    )
    for user_id in driver_ids:
        has_virtual = connection.execute(
            sa.select(id_tags.c.user_id).where(
                id_tags.c.user_id == user_id,
                id_tags.c.is_virtual.is_(True),
            )
        ).first()
        if has_virtual:
            continue
        tag_value = f"V{secrets.token_urlsafe(12)}"
        while connection.execute(
            sa.select(id_tags.c.id_tag).where(id_tags.c.id_tag == tag_value)
        ).first():
            tag_value = f"V{secrets.token_urlsafe(12)}"
        connection.execute(
            id_tags.insert().values(
                id_tag=tag_value,
                user_id=user_id,
                is_virtual=True,
                is_blocked=False,
                expiry_date=None,
            )
        )


def downgrade() -> None:
    op.drop_index("ix_remote_start_connector_created", table_name="remote_start_requests")
    op.drop_index("ix_remote_start_driver_created", table_name="remote_start_requests")
    op.drop_index("uq_remote_start_active_connector", table_name="remote_start_requests")
    op.drop_table("remote_start_requests")
    op.drop_index("uq_virtual_id_tag_per_user", table_name="id_tags")
    op.execute(sa.text("DELETE FROM id_tags WHERE is_virtual IS TRUE"))
    op.drop_column("id_tags", "is_virtual")
