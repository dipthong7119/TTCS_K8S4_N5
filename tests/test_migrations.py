from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.config import settings
from app.core.security import verify_password
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def migrated_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "migration_test.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)

    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        yield config, engine
    finally:
        engine.dispose()


def test_migrations_upgrade_and_downgrade(migrated_database) -> None:
    config, engine = migrated_database
    expected_tables = {
        "users",
        "roles",
        "user_roles",
        "stations",
        "charge_points",
        "connectors",
    }
    assert expected_tables.issubset(set(inspect(engine).get_table_names()))

    engine.dispose()
    command.downgrade(config, "base")
    downgraded_engine = create_engine(settings.DATABASE_URL)
    try:
        assert not expected_tables.intersection(inspect(downgraded_engine).get_table_names())
    finally:
        downgraded_engine.dispose()


def test_seed_contains_exactly_five_required_roles(migrated_database) -> None:
    _, engine = migrated_database
    with engine.connect() as connection:
        roles = connection.execute(text("SELECT name FROM roles ORDER BY name")).scalars().all()

    assert roles == ["accountant", "admin", "driver", "operator", "station_owner"]


def test_users_email_is_unique(migrated_database) -> None:
    _, engine = migrated_database
    insert_user = text(
        "INSERT INTO users (email, password_hash, full_name) "
        "VALUES (:email, :password_hash, :full_name)"
    )
    user = {
        "email": "duplicate@example.com",
        "password_hash": "test-hash",
        "full_name": "Duplicate User",
    }

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert_user, user)
        connection.execute(insert_user, user)


def test_seeded_demo_users_have_working_documented_passwords(migrated_database) -> None:
    _, engine = migrated_database
    documented_passwords = {
        "admin@csms.local": "Admin@2024!",
        "owner@csms.local": "Owner@2024!",
        "operator@csms.local": "Operator@2024!",
        "accountant@csms.local": "Accountant@2024!",
        "driver@csms.local": "Driver@2024!",
    }

    with engine.connect() as connection:
        users = connection.execute(
            text("SELECT email, password_hash FROM users ORDER BY email")
        ).all()

    assert len(users) == len(documented_passwords)
    for email, password_hash in users:
        assert verify_password(documented_passwords[email], password_hash), email
