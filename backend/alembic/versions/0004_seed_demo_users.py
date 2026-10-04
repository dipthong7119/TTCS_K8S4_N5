"""
Migration: seed 5 tai khoan demo (1 moi vai tro) cho moi truong dev/staging
Tham chieu: SPRINT_1.md T-05, README.md muc Tai khoan dang nhap demo
CANH BAO: khong dung tren production
"""

import sqlalchemy as sa

from alembic import op

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
    users = sa.table(
        "users",
        sa.column("id", sa.Integer),
        sa.column("email", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("full_name", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("failed_login_count", sa.Integer),
    )
    roles = sa.table("roles", sa.column("id", sa.Integer), sa.column("name", sa.String))
    user_roles = sa.table(
        "user_roles", sa.column("user_id", sa.Integer), sa.column("role_id", sa.Integer)
    )

    for u in _DEMO_USERS:
        user_id = conn.execute(
            sa.select(users.c.id).where(users.c.email == u["email"])
        ).scalar_one_or_none()
        if user_id is None:
            conn.execute(
                users.insert().values(
                    email=u["email"],
                    password_hash=u["password_hash"],
                    full_name=u["full_name"],
                    is_active=True,
                    failed_login_count=0,
                )
            )
            user_id = conn.execute(
                sa.select(users.c.id).where(users.c.email == u["email"])
            ).scalar_one()

        role_id = conn.execute(
            sa.select(roles.c.id).where(roles.c.name == u["role"])
        ).scalar_one_or_none()
        if role_id is None:
            continue
        assigned = conn.execute(
            sa.select(user_roles.c.user_id).where(
                user_roles.c.user_id == user_id, user_roles.c.role_id == role_id
            )
        ).first()
        if assigned is None:
            conn.execute(user_roles.insert().values(user_id=user_id, role_id=role_id))


def downgrade() -> None:
    conn = op.get_bind()
    users = sa.table(
        "users", sa.column("id", sa.Integer), sa.column("email", sa.String)
    )
    user_roles = sa.table("user_roles", sa.column("user_id", sa.Integer))
    for u in _DEMO_USERS:
        user_id = conn.execute(
            sa.select(users.c.id).where(users.c.email == u["email"])
        ).scalar_one_or_none()
        if user_id is not None:
            conn.execute(user_roles.delete().where(user_roles.c.user_id == user_id))
            conn.execute(users.delete().where(users.c.id == user_id))
