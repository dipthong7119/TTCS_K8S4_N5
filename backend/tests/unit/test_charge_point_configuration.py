"""Test cho S-60: cấu hình OCPP từ xa."""

import asyncio
import importlib.util
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.config import settings
from app.core.deps import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.charge_point import ChargePoint
from app.models.charge_point_configuration import ChargePointConfiguration
from app.models.station import Station
from app.models.user import User
from app.ocpp.config_keys import (
    CONFIGURATION_KEYS,
    ConfigurationValidationError,
    validate_change,
)
from app.ocpp.handlers.boot_notification import handle_boot_notification
from app.services.charge_point_configuration import (
    change_configuration,
    get_effective_heartbeat_interval,
)
from app.services.connection_manager import ConnectionManager, manager
from app.services.jobs import expire_stale_charge_points_once
from app.services.ocpp_parser import OCPPError, parse_message


@pytest.fixture
def configuration_app(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = session_factory()
    user = User(id=1, email="ops@example.test", password_hash="test", full_name="Ops")
    db.add(user)
    db.flush()
    station = Station(id=1, name="Test station", owner_id=user.id, status="active")
    db.add(station)
    db.flush()
    point = ChargePoint(
        id=1,
        code="CP-CONFIG",
        station_id=station.id,
        status="online",
        last_seen_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(point)
    db.commit()
    db.close()

    def override_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    role_holder = {"roles": ["operator"]}

    def override_user():
        return SimpleNamespace(
            id=9,
            email="not-logged@example.test",
            full_name="Operator",
            roles=[SimpleNamespace(name=role) for role in role_holder["roles"]],
        )

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    test_client = TestClient(app)
    monkeypatch.setitem(manager.active_connections, "CP-CONFIG", AsyncMock())
    try:
        yield test_client, session_factory, role_holder
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        test_client.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.mark.parametrize(
    ("key", "raw_value", "expected"),
    [
        ("HeartbeatInterval", 30, 30),
        ("HeartbeatInterval", "3600", 3600),
        ("MeterValueSampleInterval", "5", 5),
        ("MeterValueSampleInterval", 900, 900),
    ],
)
def test_validate_change_accepts_bounds(key, raw_value, expected):
    assert validate_change(key, raw_value) == expected


def test_allowlist_records_integer_type_and_ranges():
    assert all(spec.value_type is int for spec in CONFIGURATION_KEYS.values())
    assert CONFIGURATION_KEYS["HeartbeatInterval"].minimum == 30
    assert CONFIGURATION_KEYS["HeartbeatInterval"].maximum == 3600
    assert CONFIGURATION_KEYS["MeterValueSampleInterval"].minimum == 5
    assert CONFIGURATION_KEYS["MeterValueSampleInterval"].maximum == 900


@pytest.mark.parametrize(
    ("key", "raw_value", "error_code"),
    [
        ("HeartbeatInterval", 29, "out_of_range"),
        ("HeartbeatInterval", 3601, "out_of_range"),
        ("MeterValueSampleInterval", 4, "out_of_range"),
        ("MeterValueSampleInterval", 901, "out_of_range"),
        ("HeartbeatInterval", "abc", "invalid_integer"),
        ("HeartbeatInterval", 30.5, "invalid_integer"),
        ("HeartbeatInterval", "", "invalid_integer"),
        ("HeartbeatInterval", -1, "out_of_range"),
        ("HeartbeatInterval", True, "invalid_integer"),
        ("UnknownKey", 60, "unknown_key"),
        ("AuthorizationKey", "secret", "unknown_key"),
    ],
)
def test_validate_change_rejects_invalid_values(key, raw_value, error_code):
    with pytest.raises(ConfigurationValidationError) as error:
        validate_change(key, raw_value)
    assert error.value.code == error_code


@pytest.mark.parametrize(
    ("cp_status", "expected_status", "expected_http", "expected_reboot"),
    [
        ("Accepted", "applied", 200, False),
        ("RebootRequired", "reboot_required", 200, True),
    ],
)
def test_change_configuration_saves_only_successful_status(
    configuration_app,
    monkeypatch,
    cp_status,
    expected_status,
    expected_http,
    expected_reboot,
):
    client, session_factory, _ = configuration_app
    sent = []

    async def send_call(code, action, payload, timeout):
        sent.append((code, action, payload, timeout))
        return {"status": cp_status}

    monkeypatch.setattr(manager, "send_call", send_call)
    response = client.put(
        "/api/charge-points/CP-CONFIG/configuration/HeartbeatInterval",
        json={"value": "600"},
    )

    assert response.status_code == expected_http
    assert response.json() == {
        "status": expected_status,
        "value": 600,
        "reboot_required": expected_reboot,
        "verified": None,
    }
    assert sent == [
        (
            "CP-CONFIG",
            "ChangeConfiguration",
            {"key": "HeartbeatInterval", "value": "600"},
            settings.OCPP_REMOTE_CALL_TIMEOUT_SECONDS,
        )
    ]
    with session_factory() as db:
        row = db.query(ChargePointConfiguration).one()
        assert row.value == "600"
        assert row.status == expected_status
        assert row.confirmed_at is not None


@pytest.mark.parametrize(
    ("result", "http_status", "error_code"),
    [
        ({"status": "Rejected"}, 502, "configuration_rejected"),
        ({"status": "NotSupported"}, 501, "configuration_not_supported"),
        ({"call_error": True}, 502, "ocpp_call_error"),
        ({"timeout": True}, 504, "configuration_timeout"),
    ],
)
def test_failed_change_does_not_store_value(
    configuration_app,
    monkeypatch,
    result,
    http_status,
    error_code,
):
    client, session_factory, _ = configuration_app

    async def send_call(*_args, **_kwargs):
        if result.get("call_error"):
            raise OCPPError("NotSupported", "not supported")
        if result.get("timeout"):
            raise asyncio.TimeoutError
        return result

    monkeypatch.setattr(manager, "send_call", send_call)
    response = client.put(
        "/api/charge-points/CP-CONFIG/configuration/HeartbeatInterval",
        json={"value": 600},
    )
    assert response.status_code == http_status
    assert response.json()["detail"]["code"] == error_code
    with session_factory() as db:
        assert db.query(ChargePointConfiguration).count() == 0


def test_invalid_or_sensitive_key_is_rejected_before_send(configuration_app, monkeypatch):
    client, _session_factory, _ = configuration_app
    send_call = AsyncMock()
    monkeypatch.setattr(manager, "send_call", send_call)

    for key, value, code in (
        ("HeartbeatInterval", "abc", "invalid_integer"),
        ("AuthorizationKey", "secret", "unknown_key"),
    ):
        response = client.put(
            f"/api/charge-points/CP-CONFIG/configuration/{key}",
            json={"value": value},
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == code
    send_call.assert_not_awaited()


def test_reading_unapproved_key_is_rejected_before_send(configuration_app, monkeypatch):
    client, _session_factory, _ = configuration_app
    send_call = AsyncMock()
    monkeypatch.setattr(manager, "send_call", send_call)

    response = client.get(
        "/api/charge-points/CP-CONFIG/configuration",
        params={"keys": "AuthorizationKey"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unknown_key"
    send_call.assert_not_awaited()


def test_offline_configuration_change_does_not_send(configuration_app, monkeypatch):
    client, session_factory, _ = configuration_app
    with session_factory() as db:
        point = db.query(ChargePoint).one()
        point.status = "offline"
        db.commit()
    send_call = AsyncMock()
    monkeypatch.setattr(manager, "send_call", send_call)

    response = client.put(
        "/api/charge-points/CP-CONFIG/configuration/HeartbeatInterval",
        json={"value": 600},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "charge_point_offline"
    send_call.assert_not_awaited()


def test_repeating_same_change_keeps_one_row(configuration_app, monkeypatch):
    client, session_factory, _ = configuration_app
    monkeypatch.setattr(
        manager,
        "send_call",
        AsyncMock(return_value={"status": "Accepted"}),
    )
    url = "/api/charge-points/CP-CONFIG/configuration/HeartbeatInterval"
    first = client.put(url, json={"value": 600})
    second = client.put(url, json={"value": "600"})

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    with session_factory() as db:
        assert db.query(ChargePointConfiguration).count() == 1


def test_get_configuration_filters_sensitive_keys_and_reports_mismatch(
    configuration_app,
    monkeypatch,
    caplog,
):
    client, session_factory, _ = configuration_app
    with session_factory() as db:
        db.add(
            ChargePointConfiguration(
                charge_point_id=1,
                key="HeartbeatInterval",
                value="600",
                status="applied",
                confirmed_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        db.commit()

    async def send_call(code, action, payload, timeout):
        assert code == "CP-CONFIG"
        assert action == "GetConfiguration"
        assert payload == {"key": ["HeartbeatInterval", "MeterValueSampleInterval"]}
        assert timeout == settings.OCPP_REMOTE_CALL_TIMEOUT_SECONDS
        return {
            "configurationKey": [
                {"key": "HeartbeatInterval", "readonly": False, "value": "300"},
                {"key": "MeterValueSampleInterval", "readonly": True, "value": "15"},
                {"key": "AuthorizationKey", "readonly": False, "value": "VERYSECRET"},
            ],
            "unknownKey": ["MeterValueSampleInterval", "AuthorizationKey"],
        }

    monkeypatch.setattr(manager, "send_call", send_call)
    caplog.set_level(logging.WARNING)
    response = client.get(
        "/api/charge-points/CP-CONFIG/configuration",
        params=[("keys", "HeartbeatInterval"), ("keys", "MeterValueSampleInterval")],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["unknownKey"] == ["MeterValueSampleInterval"]
    assert body["configurationKey"] == [
        {
            "key": "HeartbeatInterval",
            "readonly": False,
            "value": "300",
            "requested_value": "600",
            "verified": False,
        },
        {
            "key": "MeterValueSampleInterval",
            "readonly": True,
            "value": "15",
            "requested_value": None,
            "verified": None,
        },
    ]
    assert "AuthorizationKey" not in response.text
    assert "VERYSECRET" not in response.text
    assert "AuthorizationKey" not in caplog.text
    assert "VERYSECRET" not in caplog.text
    assert "configuration mismatch" in caplog.text.lower()


@pytest.mark.parametrize("role", ["driver", "station_owner", "accountant"])
def test_configuration_routes_deny_other_roles(configuration_app, role):
    client, _session_factory, roles = configuration_app
    roles["roles"] = [role]
    response = client.put(
        "/api/charge-points/CP-CONFIG/configuration/HeartbeatInterval",
        json={"value": 600},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["operator", "admin"])
def test_configuration_routes_allow_operator_and_admin(
    configuration_app,
    monkeypatch,
    role,
):
    client, _session_factory, roles = configuration_app
    roles["roles"] = [role]
    monkeypatch.setattr(
        manager,
        "send_call",
        AsyncMock(return_value={"status": "Accepted"}),
    )
    response = client.put(
        "/api/charge-points/CP-CONFIG/configuration/HeartbeatInterval",
        json={"value": 600},
    )
    assert response.status_code == 200


def test_offline_get_returns_last_saved_values(configuration_app, monkeypatch):
    client, session_factory, _ = configuration_app
    with session_factory() as db:
        db.add(
            ChargePointConfiguration(
                charge_point_id=1,
                key="HeartbeatInterval",
                value="600",
                status="applied",
                confirmed_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        point = db.query(ChargePoint).one()
        point.status = "offline"
        db.commit()
    send_call = AsyncMock()
    monkeypatch.setattr(manager, "send_call", send_call)

    response = client.get("/api/charge-points/CP-CONFIG/configuration")
    assert response.status_code == 409
    assert response.json()["detail"]["last_saved"]["HeartbeatInterval"]["value"] == "600"
    send_call.assert_not_awaited()


def test_boot_activates_reboot_required_config_and_returns_effective_interval(
    configuration_app,
):
    _client, session_factory, _roles = configuration_app
    with session_factory() as db:
        db.add(
            ChargePointConfiguration(
                charge_point_id=1,
                key="HeartbeatInterval",
                value="600",
                status="reboot_required",
                confirmed_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        db.commit()
        point = db.query(ChargePoint).one()
        assert get_effective_heartbeat_interval(db, point) == settings.OCPP_HEARTBEAT_INTERVAL_SECONDS
        response = handle_boot_notification(db, point.code, "boot-config", {})
        frame = parse_message(response)
        assert frame[3]["interval"] == 600
        config = db.query(ChargePointConfiguration).one()
        assert config.status == "applied"


def test_boot_uses_global_heartbeat_when_not_configured(configuration_app, monkeypatch):
    _client, session_factory, _roles = configuration_app
    monkeypatch.setattr(settings, "OCPP_HEARTBEAT_INTERVAL_SECONDS", 420)
    with session_factory() as db:
        response = handle_boot_notification(db, "CP-CONFIG", "boot-global", {})
        frame = parse_message(response)
        assert frame[3]["interval"] == 420


def test_offline_job_uses_per_charge_point_heartbeat(configuration_app, monkeypatch):
    _client, session_factory, _roles = configuration_app
    monkeypatch.setattr(settings, "OCPP_HEARTBEAT_INTERVAL_SECONDS", 300)
    monkeypatch.setattr(settings, "OCPP_HEARTBEAT_MULTIPLIER", 2)
    now = datetime.now(UTC).replace(tzinfo=None)
    with session_factory() as db:
        db.add(
            ChargePointConfiguration(
                charge_point_id=1,
                key="HeartbeatInterval",
                value="600",
                status="applied",
                confirmed_at=now,
            )
        )
        point = db.query(ChargePoint).one()
        point.last_seen_at = now - timedelta(seconds=900)
        db.commit()
        assert expire_stale_charge_points_once(db) == 0
        db.refresh(point)
        assert point.status == "online"


def test_reboot_required_does_not_change_offline_threshold(configuration_app, monkeypatch):
    _client, session_factory, _roles = configuration_app
    monkeypatch.setattr(settings, "OCPP_HEARTBEAT_INTERVAL_SECONDS", 300)
    monkeypatch.setattr(settings, "OCPP_HEARTBEAT_MULTIPLIER", 2)
    now = datetime.now(UTC).replace(tzinfo=None)
    with session_factory() as db:
        db.add(
            ChargePointConfiguration(
                charge_point_id=1,
                key="HeartbeatInterval",
                value="600",
                status="reboot_required",
                confirmed_at=now,
            )
        )
        point = db.query(ChargePoint).one()
        point.last_seen_at = now - timedelta(seconds=700)
        db.commit()
        assert expire_stale_charge_points_once(db) == 1
        db.refresh(point)
        assert point.status == "offline"


@pytest.mark.asyncio
async def test_concurrent_changes_serialize_and_store_last_accepted(
    configuration_app,
    monkeypatch,
):
    _client, session_factory, _roles = configuration_app
    active_calls = 0
    max_active_calls = 0
    accepted_order: list[str] = []

    async def send_call(_code, _action, payload, _timeout):
        nonlocal active_calls, max_active_calls
        active_calls += 1
        max_active_calls = max(max_active_calls, active_calls)
        accepted_order.append(payload["value"])
        await asyncio.sleep(0.01)
        active_calls -= 1
        return {"status": "Accepted"}

    monkeypatch.setattr(manager, "send_call", send_call)
    async def change(value: int, actor_id: int) -> None:
        with session_factory() as db:
            await change_configuration(
                db, "CP-CONFIG", "HeartbeatInterval", value, actor_id
            )

    await asyncio.gather(change(600, 9), change(900, 10))
    with session_factory() as db:
        row = db.query(ChargePointConfiguration).one()
        assert max_active_calls == 1
        assert row.value == accepted_order[-1]


@pytest.mark.asyncio
async def test_waiting_call_can_receive_result_without_blocking_connection():
    class StubWebSocket:
        def __init__(self):
            self.sent = asyncio.Event()
            self.message_id = ""

        async def send_text(self, raw_message):
            frame = parse_message(raw_message)
            self.message_id = frame[1]
            self.sent.set()

    connection_manager = ConnectionManager()
    websocket = StubWebSocket()
    connection_manager.active_connections["CP-WAIT"] = websocket
    pending = asyncio.create_task(
        connection_manager.send_call("CP-WAIT", "GetConfiguration", {"key": []}, timeout=1)
    )
    await asyncio.wait_for(websocket.sent.wait(), timeout=0.5)
    resolved = await connection_manager.resolve_call_result(
        "CP-WAIT",
        websocket.message_id,
        {"configurationKey": [], "unknownKey": []},
        websocket,
    )
    assert resolved is True
    assert await pending == {"configurationKey": [], "unknownKey": []}


def test_configuration_migration_up_and_down():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "h20261009_charge_point_configuration.py"
    )
    spec = importlib.util.spec_from_file_location("configuration_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE charge_points (id INTEGER PRIMARY KEY)"
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            assert inspect(connection).has_table("charge_point_configuration")
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
            assert not inspect(connection).has_table("charge_point_configuration")
    finally:
        engine.dispose()
