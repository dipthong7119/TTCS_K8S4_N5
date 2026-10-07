import asyncio
import json
from datetime import datetime, timezone
from time import perf_counter
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.charge_point import ChargePoint, Connector
from app.models.station import Station
from app.models.user import User

engine_test = create_engine(
    "sqlite:///:memory:", 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
SessionLocalTest = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

def override_get_db():
    try:
        db = SessionLocalTest()
        yield db
    finally:
        db.close()




@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    db = SessionLocalTest()
    
    # 2 users: admin and station_owner
    admin = User(id=1, email="admin@test.com", password_hash="123", full_name="Admin")
    owner = User(id=2, email="owner@test.com", password_hash="123", full_name="Owner")
    db.add_all([admin, owner])
    
    # 2 stations
    st1 = Station(id=1, name="Station 1", owner_id=1, status="active")
    st2 = Station(id=2, name="Station 2", owner_id=2, status="active")
    db.add_all([st1, st2])
    
    # Charge points
    recent = datetime.now(timezone.utc)
    cp1 = ChargePoint(id=1, code="CP001", station_id=1, status="online", last_seen_at=recent)
    cp2 = ChargePoint(id=2, code="CP002", station_id=2, status="offline", last_seen_at=recent)
    db.add_all([cp1, cp2])
    
    # Connectors
    cn1 = Connector(id=1, charge_point_id=1, connector_id=1, status="rảnh")
    cn2 = Connector(id=2, charge_point_id=2, connector_id=1, status="bận")
    db.add_all([cn1, cn2])
    
    db.commit()
    db.close()
    
    yield
    Base.metadata.drop_all(bind=engine_test)
    engine_test.dispose()

def test_monitoring_tree_admin():
    from app.core.deps import get_current_user

    class MockRole:
        def __init__(self, name):
            self.name = name

    class MockUser:
        def __init__(self, id, roles):
            self.id = id
            self.roles = [MockRole(r) for r in roles]

    app.dependency_overrides[get_current_user] = lambda: MockUser(id=1, roles=["admin"])
    resp = client.get("/api/monitoring/tree")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "Station 1"
    assert data[0]["charge_points"][0]["connectors"][0]["status"] == "rảnh"

def test_monitoring_tree_owner():
    from app.core.deps import get_current_user

    class MockRole:
        def __init__(self, name):
            self.name = name

    class MockUser:
        def __init__(self, id, roles):
            self.id = id
            self.roles = [MockRole(r) for r in roles]

    app.dependency_overrides[get_current_user] = lambda: MockUser(id=2, roles=["station_owner"])
    resp = client.get("/api/monitoring/tree")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Station 2"
    # A connector cannot be reported as available/busy while its charge point
    # is offline; the monitoring tree deliberately exposes that state as unknown.
    assert data[0]["charge_points"][0]["connectors"][0]["status"] == "unknown"


def test_monitoring_tree_loads_50_charge_points_in_one_query_under_200ms():
    from app.routers.monitoring import get_monitoring_tree

    db = SessionLocalTest()
    station = db.query(Station).filter_by(id=1).one()
    first_point = db.query(ChargePoint).filter_by(id=1).one()
    first_point.last_seen_at = datetime.now(timezone.utc)
    db.add_all(
        Connector(charge_point_id=first_point.id, connector_id=index, status="rảnh")
        for index in range(2, 5)
    )
    for point_number in range(2, 51):
        point = ChargePoint(
            code=f"CP-{point_number:02d}",
            station_id=station.id,
            status="online",
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(point)
        db.flush()
        db.add_all(
            Connector(charge_point_id=point.id, connector_id=index, status="rảnh")
            for index in range(1, 5)
        )
    db.commit()

    statements = []
    def record_query(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement)

    event.listen(engine_test, "before_cursor_execute", record_query)
    started = perf_counter()
    try:
        tree = asyncio.run(
            get_monitoring_tree(
                SimpleNamespace(id=1, roles=[SimpleNamespace(name="admin")]),
                db,
            )
        )
        elapsed = perf_counter() - started
    finally:
        event.remove(engine_test, "before_cursor_execute", record_query)
        db.close()

    points = tree[0]["charge_points"]
    assert len(points) == 50
    assert sum(len(point["connectors"]) for point in points) == 200
    assert len(statements) == 1
    assert elapsed < 0.2


def test_status_updates_are_filtered_by_station_owner(monkeypatch):
    from app.routers import monitoring

    owner_queue = asyncio.Queue()
    other_owner_queue = asyncio.Queue()
    operator_queue = asyncio.Queue()
    monkeypatch.setattr(
        monitoring,
        "sse_clients",
        [
            {"owner_id": 7, "global_access": False, "queue": owner_queue},
            {"owner_id": 8, "global_access": False, "queue": other_owner_queue},
            {"owner_id": 99, "global_access": True, "queue": operator_queue},
        ],
    )

    monitoring.notify_status_change(12, [{"code": "CP-12"}], owner_id=7)

    assert owner_queue.qsize() == 1
    assert other_owner_queue.empty()
    assert operator_queue.qsize() == 1

@pytest.fixture(scope="function", autouse=True)
def apply_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

client = TestClient(app)

def test_publish_charge_point_status_uses_station_payload(monkeypatch):
    from app.routers import monitoring
    from app.services.ocpp_handlers import publish_charge_point_status

    queue = asyncio.Queue()
    monkeypatch.setattr(
        monitoring,
        "sse_clients",
        [{"owner_id": 2, "global_access": False, "queue": queue}],
    )

    db = SessionLocalTest()
    # cp2 is offline, its connector cn2 has status 'bận'
    # The payload should mark connector as 'unknown' due to station_status_payload logic.
    publish_charge_point_status(db, 2)
    db.close()

    assert queue.qsize() == 1
    event = queue.get_nowait()
    assert event["event"] == "status_update"
    data = json.loads(event["data"])
    assert data["station_id"] == 2
    assert len(data["charge_points"]) == 1
    cp = data["charge_points"][0]
    assert cp["status"] == "offline"
    assert cp["connectors"][0]["status"] == "unknown"


def test_sse_queue_limit_drops_oldest_event(monkeypatch):
    from app.routers import monitoring

    # queue size 10
    queue = asyncio.Queue(maxsize=monitoring.SSE_QUEUE_LIMIT)
    monkeypatch.setattr(
        monitoring,
        "sse_clients",
        [{"owner_id": 1, "global_access": True, "queue": queue}],
    )

    # Fill the queue
    for i in range(monitoring.SSE_QUEUE_LIMIT):
        monitoring.notify_status_change(1, [{"id": i}], owner_id=1)

    assert queue.qsize() == monitoring.SSE_QUEUE_LIMIT

    # Add one more
    monitoring.notify_status_change(1, [{"id": 999}], owner_id=1)
    assert queue.qsize() == monitoring.SSE_QUEUE_LIMIT

    # The first event was dropped. The oldest now should be id=1.
    event = queue.get_nowait()
    data = json.loads(event["data"])
    assert data["charge_points"][0]["id"] == 1


def test_status_updates_are_not_sent_to_drivers(monkeypatch):
    from app.routers import monitoring

    driver_queue = asyncio.Queue()
    monkeypatch.setattr(
        monitoring,
        "sse_clients",
        [{"owner_id": None, "driver_id": 3, "global_access": False, "queue": driver_queue}],
    )

    monitoring.notify_status_change(1, [{"code": "CP-1"}], owner_id=1)

    assert driver_queue.empty()
