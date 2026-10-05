"""Regression checks for gaps found against Sprint 1/2 Tasks and Backlog."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import event

from app.config import Settings, settings
from app.main import app
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.services.ocpp_handlers import (
    handle_ocpp_message,
    publish_charge_point_status,
    touch_last_seen,
)
from app.services.ocpp_parser import pack_call, parse_message


@pytest.fixture
def point(db_session, user_factory):
    owner = user_factory()
    station = Station(name="Acceptance station", owner_id=owner.id, status="active")
    charge_point = ChargePoint(code="AC-POINT", station=station, status="online")
    charge_point.last_seen_at = datetime.now(UTC).replace(tzinfo=None)
    charge_point.connectors = [Connector(connector_id=1, status="bận")]
    db_session.add(charge_point)
    db_session.commit()
    return charge_point


def test_rejected_boot_turns_previously_online_point_offline(db_session, point):
    point.station.status = "locked"
    db_session.commit()
    response = handle_ocpp_message(db_session, point.code, pack_call("locked", "BootNotification", {}))
    db_session.refresh(point)
    assert parse_message(response)[3]["status"] == "Rejected"
    assert point.status == "offline"
    assert point.connectors[0].status == "unknown"


def test_heartbeat_recovery_without_offline_job_clears_old_connector_state(db_session, point):
    point.last_seen_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
    db_session.commit()
    response = handle_ocpp_message(db_session, point.code, pack_call("recover", "Heartbeat", {}))
    db_session.refresh(point)
    assert parse_message(response)[0] == 3
    assert point.status == "online"
    assert point.connectors[0].status == "unknown"


def test_overall_ocpp_status_is_persisted_without_changing_live_connectors(db_session, point):
    raw = pack_call("whole-point", "StatusNotification", {"connectorId": 0, "status": "Faulted"})
    response = handle_ocpp_message(db_session, point.code, raw)
    db_session.refresh(point)
    assert parse_message(response)[3] == {}
    assert point.ocpp_status == "Faulted"
    assert point.connectors[0].status == "bận"


def test_connector_error_clears_on_recovery_and_keeps_history(db_session, point):
    for msg_id, status, error in [("fault", "Faulted", "GroundFailure"), ("ok", "Available", "NoError")]:
        raw = pack_call(msg_id, "StatusNotification", {"connectorId": 1, "status": status, "errorCode": error})
        assert parse_message(handle_ocpp_message(db_session, point.code, raw))[0] == 3
        db_session.refresh(point.connectors[0])
        assert point.connectors[0].error_code == error
    assert len(point.connectors[0].errors) == 1


def test_heartbeat_configuration_uses_one_value_for_old_and_new_names(monkeypatch):
    monkeypatch.delenv("OCPP_HEARTBEAT_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("HEARTBEAT_INTERVAL", raising=False)
    config = Settings(_env_file=None, HEARTBEAT_INTERVAL=7)
    assert config.OCPP_HEARTBEAT_INTERVAL_SECONDS == config.HEARTBEAT_INTERVAL == 7
    config.HEARTBEAT_INTERVAL = 9
    assert config.OCPP_HEARTBEAT_INTERVAL_SECONDS == 9
    monkeypatch.setenv("HEARTBEAT_INTERVAL", "5")
    monkeypatch.setenv("OCPP_HEARTBEAT_INTERVAL_SECONDS", "11")
    config = Settings(_env_file=None)
    assert config.HEARTBEAT_INTERVAL == 11


def test_new_application_route_denies_even_admin_without_role_declaration(client, user_factory):
    admin = user_factory(email="guard-admin@example.com", role_name="admin")
    assert client.post("/api/auth/login", json={"email": admin.email, "password": "ValidPassword123!"}).status_code == 200
    original_routes = list(app.router.routes)
    try:
        @app.get("/api/acceptance-unannotated")
        async def probe():
            return {"exposed": True}

        assert client.get("/api/acceptance-unannotated").status_code == 403
        assert client.get("/health").status_code == 200
    finally:
        app.router.routes[:] = original_routes


def test_charge_point_code_can_change_only_before_first_session(client, db_session, point):
    owner = point.station.owner
    assert client.post("/api/auth/login", json={"email": owner.email, "password": "ValidPassword123!"}).status_code == 200
    response = client.patch(f"/api/charge-points/{point.id}", json={"code": "RENAMED-POINT"})
    assert response.status_code == 200, response.text
    assert response.json()["code"] == "RENAMED-POINT"
    db_session.add(ChargingSession(
        charge_point_id=point.id, charge_point_code=point.code, station_id=point.station_id,
        station_name=point.station.name, connector_number=1, meter_start_wh=0,
        started_at=datetime.now(UTC).replace(tzinfo=None),
    ))
    db_session.commit()
    response = client.patch(f"/api/charge-points/{point.id}", json={"code": "FORBIDDEN"})
    assert response.status_code == 409, response.text
    assert "phiên sạc" in response.json()["detail"]
    assert client.delete(f"/api/charge-points/{point.id}").status_code == 409


def test_boot_advertises_canonical_interval(db_session, point, monkeypatch):
    monkeypatch.setattr(settings, "OCPP_HEARTBEAT_INTERVAL_SECONDS", 23)
    response = handle_ocpp_message(db_session, point.code, pack_call("interval", "BootNotification", {}))
    assert parse_message(response)[3]["interval"] == 23


def test_documented_environment_example_loads_without_extra_field_errors():
    example = Path(__file__).resolve().parents[1] / ".env.example"
    assert Settings(_env_file=example).CSMS_BACKUP_RETENTION_DAYS >= 1


def test_last_seen_uses_one_column_update_and_database_time(db_session, point):
    old_updated_at = datetime(2000, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    point.updated_at = old_updated_at
    db_session.commit()
    statements = []

    def capture(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        touch_last_seen(db_session, point.code)
        db_session.commit()
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    db_session.refresh(point)
    updates = [sql for sql in statements if sql.startswith("UPDATE charge_points")]
    assert updates == ["UPDATE charge_points SET last_seen_at = CURRENT_TIMESTAMP WHERE code = ?"]
    assert point.updated_at == old_updated_at
    assert abs((datetime.now(UTC).replace(tzinfo=None) - point.last_seen_at).total_seconds()) < 2


def test_realtime_snapshot_uses_one_query_and_filters_the_owner(db_session, point, monkeypatch):
    from app.routers import monitoring

    owner_queue, other_queue = asyncio.Queue(), asyncio.Queue()
    monkeypatch.setattr(monitoring, "sse_clients", [
        {"global_access": False, "owner_id": point.station.owner_id, "queue": owner_queue},
        {"global_access": False, "owner_id": -1, "queue": other_queue},
    ])
    point_id = point.id
    db_session.expire_all()
    statements = []

    def capture(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        publish_charge_point_status(db_session, point_id)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert len(statements) == 1
    snapshot = json.loads(owner_queue.get_nowait()["data"])
    assert snapshot["charge_points"][0]["connectors"][0]["status"] == "bận"
    assert other_queue.empty()
