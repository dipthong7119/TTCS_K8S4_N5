"""Kiểm migration T-51 tiến/lùi trên SQLite tạm."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_remote_start_migration_upgrade_and_downgrade(tmp_path: Path):
    database = tmp_path / "remote_start_migration.db"
    engine = sa.create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT)")
        connection.exec_driver_sql("CREATE TABLE roles (id INTEGER PRIMARY KEY, name TEXT)")
        connection.exec_driver_sql(
            "CREATE TABLE user_roles (user_id INTEGER, role_id INTEGER)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE id_tags (id INTEGER PRIMARY KEY, id_tag VARCHAR(50) UNIQUE, "
            "user_id INTEGER NOT NULL, is_blocked BOOLEAN NOT NULL DEFAULT 0, "
            "expiry_date DATETIME, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
        connection.exec_driver_sql("CREATE TABLE connectors (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE charging_sessions (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO users (id, email) VALUES (1, 'driver@test')")
        connection.exec_driver_sql("INSERT INTO roles (id, name) VALUES (1, 'driver')")
        connection.exec_driver_sql("INSERT INTO user_roles VALUES (1, 1)")

        migration_path = (
            Path(__file__).resolve().parents[2]
            / "alembic"
            / "versions"
            / "h20261011_remote_start_requests.py"
        )
        spec = importlib.util.spec_from_file_location("remote_start_migration", migration_path)
        assert spec is not None and spec.loader is not None
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()
        inspector = sa.inspect(connection)
        assert "is_virtual" in {column["name"] for column in inspector.get_columns("id_tags")}
        assert inspector.has_table("remote_start_requests")
        virtual_count = connection.exec_driver_sql(
            "SELECT COUNT(*) FROM id_tags WHERE is_virtual = 1"
        ).scalar_one()
        assert virtual_count == 1

        with Operations.context(context):
            migration.downgrade()
        inspector = sa.inspect(connection)
        assert not inspector.has_table("remote_start_requests")
        assert "is_virtual" not in {column["name"] for column in inspector.get_columns("id_tags")}
    engine.dispose()
