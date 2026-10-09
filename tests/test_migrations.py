import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.config import settings
from app.core.security import verify_password


@pytest.fixture
def migrated_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request):
    database_path = tmp_path / "migration_test.db"
    database_url = request.config.getoption("--migration-database-url")
    admin_engine = None
    schema = None
    if database_url:
        admin_engine = create_engine(database_url)
        schema = f"migration_test_{uuid4().hex}"
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = make_url(database_url).update_query_dict({"options": f"-csearch_path={schema}"})
        database_url = url.render_as_string(hide_password=False)
    else:
        database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)

    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option("script_location", str(backend_dir / "alembic"))

    engine = create_engine(database_url)
    try:
        command.upgrade(config, "head")
        yield config, engine
    finally:
        engine.dispose()
        if admin_engine is not None:
            try:
                with admin_engine.begin() as connection:
                    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            finally:
                admin_engine.dispose()


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


def test_configuration_and_payment_migrations_share_one_head(migrated_database) -> None:
    config, engine = migrated_database
    assert len(ScriptDirectory.from_config(config).get_heads()) == 1
    assert {"charge_point_configuration", "payment_transactions"}.issubset(
        set(inspect(engine).get_table_names())
    )


def test_seed_contains_exactly_five_required_roles(migrated_database) -> None:
    _, engine = migrated_database
    with engine.connect() as connection:
        roles = connection.execute(text("SELECT name FROM roles ORDER BY name")).scalars().all()

    assert roles == ["accountant", "admin", "driver", "operator", "station_owner"]


def test_meter_review_migration_preserves_existing_sessions(migrated_database):
    config, engine = migrated_database
    previous_revision = "h20261006_meter_values"
    command.downgrade(config, previous_revision)
    with engine.begin() as db:
        db.execute(text(
            "INSERT INTO charging_sessions "
            "(charge_point_code, station_name, connector_number, meter_start_wh, started_at) "
            "VALUES ('MIGRATION-TEST', 'Migration station', 1, 12500, CURRENT_TIMESTAMP)"
        ))
    command.upgrade(config, "head")
    with engine.begin() as db:
        row = db.execute(text(
            "SELECT meter_start_wh, needs_review, review_reason FROM charging_sessions "
            "WHERE charge_point_code = 'MIGRATION-TEST'"
        )).one()
        assert row[0] == 12500 and not row[1] and row[2] is None
        db.execute(text(
            "UPDATE charging_sessions SET needs_review = true, review_reason = 'meter_value_decreased' "
            "WHERE charge_point_code = 'MIGRATION-TEST'"
        ))
    command.downgrade(config, previous_revision)
    assert not {"needs_review", "review_reason"}.intersection(
        column["name"] for column in inspect(engine).get_columns("charging_sessions")
    )
    with engine.connect() as db:
        assert db.execute(text(
            "SELECT meter_start_wh FROM charging_sessions WHERE charge_point_code = 'MIGRATION-TEST'"
        )).scalar_one() == 12500
    command.upgrade(config, "head")


def test_postgres_version_table_holds_all_revision_ids(migrated_database):
    config, engine = migrated_database
    if engine.dialect.name == "postgresql":
        column = next(item for item in inspect(engine).get_columns("alembic_version") if item["name"] == "version_num")
        longest = max(len(revision.revision) for revision in ScriptDirectory.from_config(config).walk_revisions())
        assert column["type"].length >= longest


def test_development_seed_works_after_migrations_and_is_repeatable(migrated_database):
    _, engine = migrated_database
    backend = Path(__file__).resolve().parents[1] / "backend"
    env = os.environ.copy()
    env.update({"DATABASE_URL": settings.DATABASE_URL, "APP_ENV": "development",
                "CSMS_ENV_FILE": str(backend.parent / ".env.example")})
    counts = []
    for _ in range(2):
        result = subprocess.run([sys.executable, "seed_data.py"], cwd=backend, env=env,
                                capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        with engine.connect() as db:
            counts.append({table: db.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one()
                           for table in ["stations", "charge_points", "connectors", "connector_errors", "charging_sessions", "id_tags", "wallet_ledger"]})
    assert counts[0] == counts[1]
    assert counts[0]["charge_points"] >= 20 and counts[0]["connector_errors"] >= 1


def test_new_connector_default_matches_sprint_one_schema(migrated_database) -> None:
    _, engine = migrated_database
    status_column = next(
        column for column in inspect(engine).get_columns("connectors") if column["name"] == "status"
    )

    assert status_column["default"].split("::")[0].strip("'\"") == "unknown"


def test_id_tag_code_is_unique(migrated_database) -> None:
    _, engine = migrated_database
    with engine.connect() as connection:
        driver_id = connection.execute(
            text(
                "SELECT users.id FROM users "
                "JOIN user_roles ON user_roles.user_id = users.id "
                "JOIN roles ON roles.id = user_roles.role_id "
                "WHERE roles.name = 'driver' ORDER BY users.id LIMIT 1"
            )
        ).scalar_one()

    insert_tag = text(
        "INSERT INTO id_tags (id_tag, user_id, is_blocked) "
        "VALUES ('UNIQUE-TAG-TEST', :user_id, FALSE)"
    )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert_tag, {"user_id": driver_id})
        connection.execute(insert_tag, {"user_id": driver_id})


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


def test_connector_error_history_survives_schema_upgrade_and_downgrade(migrated_database):
    config, engine = migrated_database
    with engine.begin() as connection:
        owner_id = connection.execute(text("SELECT id FROM users LIMIT 1")).scalar_one()
        station_id = connection.execute(
            text("INSERT INTO stations(name,owner_id) VALUES('History test',:owner) RETURNING id"),
            {"owner": owner_id},
        ).scalar_one()
        point_id = connection.execute(
            text("INSERT INTO charge_points(code,station_id) VALUES('HISTORY-POINT',:station) RETURNING id"),
            {"station": station_id},
        ).scalar_one()
        connector_id = connection.execute(
            text("INSERT INTO connectors(charge_point_id,connector_id) VALUES(:point,1) RETURNING id"),
            {"point": point_id},
        ).scalar_one()
        connection.execute(
            text("INSERT INTO connector_errors(connector_id,error_code,occurred_at) VALUES(:connector,'GroundFailure','2020-01-02 03:04:05')"),
            {"connector": connector_id},
        )
    command.downgrade(config, "h20261002_t19_status")
    with engine.connect() as connection:
        value = connection.execute(text("SELECT timestamp FROM connector_errors")).scalar_one()
        assert str(value) == "2020-01-02 03:04:05"
    command.upgrade(config, "head")
    with engine.connect() as connection:
        value = connection.execute(text("SELECT occurred_at FROM connector_errors")).scalar_one()
        assert str(value) == "2020-01-02 03:04:05"


def test_station_owner_cannot_be_deleted_with_an_existing_station(migrated_database):
    _, engine = migrated_database
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            connection.execute(text("PRAGMA foreign_keys=ON"))
        owner_id = connection.execute(text("SELECT id FROM users WHERE email='owner@csms.local'")).scalar_one()
        connection.execute(text("INSERT INTO stations(name,owner_id) VALUES('FK test',:owner)"), {"owner": owner_id})
        connection.commit()
        with pytest.raises(IntegrityError):
            connection.execute(text("DELETE FROM users WHERE id=:owner"), {"owner": owner_id})
        connection.rollback()
