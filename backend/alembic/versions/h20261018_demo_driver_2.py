"""Add a second development driver account for reservation flow demos."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "h20261018_demo_driver_2"
down_revision: str | None = "h20261018_privacy_page_compat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EMAIL = "driver2@csms.local"
_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=2,p=2$7axlhm0BOkgHTjz8ct1dxA$"
    "t8vsz7gF2am/rv3EDu3ytSVRIOiNIRLloeu/tDOeWjE"
)


def upgrade() -> None:
    connection = op.get_bind()
    user_id = connection.execute(
        sa.text("SELECT id FROM users WHERE email = :email"), {"email": _EMAIL}
    ).scalar_one_or_none()

    if user_id is None:
        connection.execute(
            sa.text(
                "INSERT INTO users "
                "(email, password_hash, full_name, is_active, failed_login_count) "
                "VALUES (:email, :password_hash, :full_name, TRUE, 0)"
            ),
            {
                "email": _EMAIL,
                "password_hash": _PASSWORD_HASH,
                "full_name": "Tai Xe Demo 2",
            },
        )
        user_id = connection.execute(
            sa.text("SELECT id FROM users WHERE email = :email"),
            {"email": _EMAIL},
        ).scalar_one()

    role_id = connection.execute(
        sa.text("SELECT id FROM roles WHERE name = 'driver'")
    ).scalar_one_or_none()
    if role_id is None:
        raise RuntimeError("Required 'driver' role is missing while seeding demo driver")

    assigned = connection.execute(
        sa.text(
            "SELECT 1 FROM user_roles WHERE user_id = :user_id AND role_id = :role_id"
        ),
        {"user_id": user_id, "role_id": role_id},
    ).first()
    if assigned is None:
        connection.execute(
            sa.text(
                "INSERT INTO user_roles (user_id, role_id) "
                "VALUES (:user_id, :role_id)"
            ),
            {"user_id": user_id, "role_id": role_id},
        )

    id_tag = f"DEMO-DRIVER-{user_id:04d}"
    existing_tag_owner = connection.execute(
        sa.text("SELECT user_id FROM id_tags WHERE id_tag = :id_tag"),
        {"id_tag": id_tag},
    ).scalar_one_or_none()
    if existing_tag_owner is not None and existing_tag_owner != user_id:
        raise RuntimeError(f"Demo RFID {id_tag} is already assigned to another user")
    if existing_tag_owner is None:
        connection.execute(
            sa.text(
                "INSERT INTO id_tags (id_tag, user_id, is_virtual, is_blocked) "
                "VALUES (:id_tag, :user_id, FALSE, FALSE)"
            ),
            {"id_tag": id_tag, "user_id": user_id},
        )


def downgrade() -> None:
    connection = op.get_bind()
    user_id = connection.execute(
        sa.text("SELECT id FROM users WHERE email = :email"), {"email": _EMAIL}
    ).scalar_one_or_none()
    if user_id is None:
        return

    connection.execute(
        sa.text("DELETE FROM id_tags WHERE user_id = :user_id AND id_tag = :id_tag"),
        {"user_id": user_id, "id_tag": f"DEMO-DRIVER-{user_id:04d}"},
    )
    connection.execute(
        sa.text("DELETE FROM user_roles WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    connection.execute(
        sa.text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id}
    )
