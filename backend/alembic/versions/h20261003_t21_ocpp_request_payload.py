"""Store the original CALL frame with its persisted response.

Revision ID: h20261003_t21_ocpp_request_payload
Revises: df03d362bc53
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261003_t21_ocpp_request_payload"
down_revision: str | None = "df03d362bc53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Keep this already-used revision ID stable. PostgreSQL enforces Alembic's
    # default VARCHAR(32), unlike SQLite, and this ID is longer than 32 chars.
    # Widen before Alembic writes the ID at the end of this migration.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        version_column = next(
            column for column in sa.inspect(bind).get_columns("alembic_version")
            if column["name"] == "version_num"
        )
        if version_column["type"].length < 64:
            op.alter_column(
                "alembic_version", "version_num", existing_type=sa.String(32),
                type_=sa.String(64), existing_nullable=False,
            )
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("ocpp_messages")
    }
    if "request_payload" not in columns:
        op.add_column(
            "ocpp_messages",
            sa.Column("request_payload", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    # Leave the version table wide: Alembic still holds this long ID until
    # after downgrade() returns. Base rollback removes all application tables.
    columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("ocpp_messages")
    }
    if "request_payload" in columns:
        op.drop_column("ocpp_messages", "request_payload")
