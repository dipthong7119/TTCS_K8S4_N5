"""SCRUM-94 (BE): current driver session API and MeterValues SSE updates."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.charge_point import ChargePoint
from app.models.charging_session import ChargingSession
from app.models.meter_value import MeterValue
from app.models.station import Station
from app.models.user import User


class MockRole:
    def __init__(self, name: str):
        self.name = name


class MockUser:
    def __init__(self, user_id: int, role: str = "driver"):
        self.id = user_id
        self.roles = [MockRole(role)]


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: MockUser(1)
    yield TestClient(app)
    app.dependency_overrides.clear()


def add_active_session(db, *, session_id: int, driver_id: int):
    owner = User(
        id=100 + session_id,
        email=f"owner-{session_id}@example.test",
        password_hash="test",
        full_name="Station Owner",
    )
    driver = User(
        id=driver_id,
        email=f"driver-{driver_id}@example.test",
        password_hash="test",
        full_name="Driver",
    )
    station = Station(id=100 + session_id, name="Live Station", owner_id=owner.id, status="active")
    point = ChargePoint(
        id=100 + session_id,
        code=f"LIVE-{session_id}",
        station_id=station.id,
        status="online",
    )
    session = ChargingSession(
        id=session_id,
        charge_point_id=point.id,
        charge_point_code=point.code,
        station_id=station.id,
        station_name=station.name,
        connector_number=1,
        user_id=driver.id,
        driver_name=driver.full_name,
        meter_start_wh=1000,
        started_at=datetime(2026, 10, 12, 7, tzinfo=UTC).replace(tzinfo=None),
        status="active",
    )
    db.add_all([owner, driver, station, point, session])
    db.commit()
    return point, session


def test_current_session_returns_latest_scrum55_energy_in_one_query(client, db):
    _, session = add_active_session(db, session_id=201, driver_id=1)
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add_all(
        [
            MeterValue(
                session_id=session.id,
                measured_at=now - timedelta(minutes=1),
                measurand="Energy.Active.Import.Register",
                value=2000,
                unit="Wh",
            ),
            MeterValue(
                session_id=session.id,
                measured_at=now,
                measurand="Power.Active.Import",
                value=9000,
                unit="W",
            ),
            MeterValue(
                session_id=session.id,
                measured_at=now,
                measurand="Energy.Active.Import.Register",
                value=3500,
                unit="Wh",
            ),
        ]
    )
    db.commit()

    statements = []

    def record_query(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", record_query)
    try:
        response = client.get("/api/sessions/current")
    finally:
        event.remove(engine, "before_cursor_execute", record_query)

    assert response.status_code == 200
    assert response.json()["id"] == session.id
    assert response.json()["live_kwh"] == 2.5
    assert len(statements) == 1


def test_current_session_is_scoped_to_authenticated_driver(client, db):
    _, session = add_active_session(db, session_id=202, driver_id=2)

    assert client.get("/api/sessions/current").status_code == 204
    assert client.get(f"/api/sessions/{session.id}").status_code == 403


def test_current_session_requires_driver_role(client, monkeypatch):
    monkeypatch.setitem(
        app.dependency_overrides,
        get_current_user,
        lambda: MockUser(1, role="operator"),
    )

    assert client.get("/api/sessions/current").status_code == 403


def test_meter_value_session_update_is_delivered_only_to_that_driver(db, monkeypatch):
    point, session = add_active_session(db, session_id=203, driver_id=1)
    driver_queue = asyncio.Queue()
    other_driver_queue = asyncio.Queue()
    operator_queue = asyncio.Queue()
    from app.routers import monitoring

    monkeypatch.setattr(
        monitoring,
        "sse_clients",
        [
            {"owner_id": None, "driver_id": 1, "global_access": False, "queue": driver_queue},
            {"owner_id": None, "driver_id": 2, "global_access": False, "queue": other_driver_queue},
            {"owner_id": None, "driver_id": None, "global_access": True, "queue": operator_queue},
        ],
    )

    from app.services.ocpp_handlers import publish_session_update

    publish_session_update(
        db,
        point.id,
        "MeterValues",
        {"transactionId": session.id, "connectorId": 1},
    )

    assert driver_queue.get_nowait() == {
        "event": "session_update",
        "data": '{"session_id": 203}',
    }
    assert other_driver_queue.empty()
    assert operator_queue.qsize() == 1
    assert operator_queue.get_nowait()["event"] == "session_update"
