"""Seed one synthetic OCPP card for each demo driver without a card yet."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7aa03e59214"
down_revision: str | None = "a6d2f891c104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    drivers = connection.execute(
        sa.text(
            "SELECT DISTINCT users.id FROM users "
            "JOIN user_roles ON user_roles.user_id = users.id "
            "JOIN roles ON roles.id = user_roles.role_id "
            "WHERE roles.name = :role ORDER BY users.id"
        ),
        {"role": "driver"},
    ).scalars()
    for user_id in drivers:
        has_tag = connection.execute(
            sa.text("SELECT id FROM id_tags WHERE user_id = :user_id LIMIT 1"),
            {"user_id": user_id},
        ).first()
        if has_tag:
            continue
        id_tag = f"DEMO-DRIVER-{user_id:04d}"
        connection.execute(
            sa.text(
                "INSERT INTO id_tags (id_tag, user_id, is_blocked) "
                "VALUES (:id_tag, :user_id, FALSE)"
            ),
            {"id_tag": id_tag, "user_id": user_id},
        )


def downgrade() -> None:
    connection = op.get_bind()
    drivers = connection.execute(
        sa.text(
            "SELECT DISTINCT users.id FROM users "
            "JOIN user_roles ON user_roles.user_id = users.id "
            "JOIN roles ON roles.id = user_roles.role_id "
            "WHERE roles.name = :role"
        ),
        {"role": "driver"},
    ).scalars()
    for user_id in drivers:
        connection.execute(
            sa.text(
                "DELETE FROM id_tags WHERE id_tag = :id_tag AND user_id = :user_id"
            ),
            {"id_tag": f"DEMO-DRIVER-{user_id:04d}", "user_id": user_id},
        )
