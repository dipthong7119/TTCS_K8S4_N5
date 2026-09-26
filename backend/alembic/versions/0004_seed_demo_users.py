"""
Migration: seed 5 tai khoan demo (1 moi vai tro) cho moi truong dev/staging
Tham chieu: SPRINT_1.md T-05, README.md muc Tai khoan dang nhap demo
CANH BAO: khong dung tren production
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_seed_demo_users"
down_revision = "0003_create_charge_points"
branch_labels = None
depends_on = None

# Hash argon2id tao truoc de migration chay nhanh (khong can import app)
_DEMO_USERS = [
    {
        "email": "admin@csms.local",
        "password_hash": "$argon2id$v=19$m=65536,t=2,p=2$eBllLULr6mx3+xQ1kujRHA$4OPrEtVpy+hE6mRI0cxdz1OBYi4tt+5U7puUnXskiO0",
        "full_name": "Quan tri vien",
        "role": "admin",
    },
    {
        "email": "owner@csms.local",
        "password_hash": "$argon2id$v=19$m=65536,t=2,p=2$7RVsGm7Gz1sE+5C6g0kX5Q$Qs0y66C2pgx8bXtJFdvvOJNivqADuyMkZpsyMoz5BQY",
        "full_name": "Chu Tram Demo",
        "role": "station_owner",
    },
    {
        "email": "operator@csms.local",
        "password_hash": "$argon2id$v=19$m=65536,t=2,p=2$8y3g3z58610Xi53ZDGRu3g$5xevnVzG4XCGPU69w3ZfbCohXaoltUv12LtNEddh+JQ",
        "full_name": "Van Hanh Vien Demo",
        "role": "operator",
    },
    {
        "email": "accountant@csms.local",
        "password_hash": "$argon2id$v=19$m=65536,t=2,p=2$PLObzNiiOaC5qw75amy+hA$bHLYbHxnkfugtGNPhXknAgx0OYTC3ip0xbos+O6FLrY",
        "full_name": "Ke Toan Demo",
        "role": "accountant",
    },
    {
        "email": "driver@csms.local",
        "password_hash": "$argon2id$v=19$m=65536,t=2,p=2$7T8z+z075vbUiQoVXUkVpQ$tLeVsRh95UfyhzTagvt9YJsfBTmYkjeyc4bBii51u2o",
        "full_name": "Tai Xe Demo",
        "role": "driver",
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    for u in _DEMO_USERS:
        # Idempotent: bo qua neu email da ton tai
        exists = conn.execute(
            sa.text("SELECT id FROM users WHERE email = :e"),
            {"e": u["email"]},
        ).fetchone()
        if exists:
            continue

        # Chen user
        result = conn.execute(
            sa.text(
                "INSERT INTO users (email, password_hash, full_name, is_active, failed_login_count) "
                "VALUES (:email, :pw, :name, 1, 0)"
            ),
            {"email": u["email"], "pw": u["password_hash"], "name": u["full_name"]},
        )
        user_id = result.lastrowid

        # Lay role_id
        role_row = conn.execute(
            sa.text("SELECT id FROM roles WHERE name = :r"),
            {"r": u["role"]},
        ).fetchone()
        if role_row:
            conn.execute(
                sa.text("INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (:u, :r)"),
                {"u": user_id, "r": role_row[0]},
            )


def downgrade() -> None:
    conn = op.get_bind()
    for u in _DEMO_USERS:
        row = conn.execute(
            sa.text("SELECT id FROM users WHERE email = :e"), {"e": u["email"]}
        ).fetchone()
        if row:
            conn.execute(sa.text("DELETE FROM user_roles WHERE user_id = :id"), {"id": row[0]})
            conn.execute(sa.text("DELETE FROM users WHERE id = :id"), {"id": row[0]})
