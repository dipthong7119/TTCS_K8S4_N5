from datetime import datetime, timezone
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.models.user import User
from app.services.connection_manager import manager

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



client = TestClient(app)

@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    db = SessionLocalTest()
    user = User(id=1, email="admin@test.com", password_hash="123", full_name="Admin")
    station = Station(id=1, name="Station", owner_id=1, status="active")
    point = ChargePoint(
        id=1,
        code="CP01",
        station_id=1,
        status="offline",
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add_all([user, station, point])
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine_test)

def test_reset_offline():
    class MockRole:
        def __init__(self, name):
            self.name = name
    class MockUser:
        def __init__(self, id, roles):
            self.id = id
            self.email = "admin@test.com"
            self.full_name = "Admin"
            self.roles = [MockRole(r) for r in roles]
            
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])
    
    resp = client.post("/api/charge_points/CP01/reset", json={"type": "Soft"})
    assert resp.status_code == 409
    assert "ngoại tuyến" in resp.json()["detail"]

def test_reset_online(monkeypatch):
    class MockRole:
        def __init__(self, name):
            self.name = name
    class MockUser:
        def __init__(self, id, roles):
            self.id = id
            self.email = "admin@test.com"
            self.full_name = "Admin"
            self.roles = [MockRole(r) for r in roles]
            
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])
    db = SessionLocalTest()
    point = db.query(ChargePoint).filter_by(code="CP01").one()
    point.status = "online"
    point.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.close()
    monkeypatch.setitem(manager.active_connections, "CP01", mock.AsyncMock())
    
    async def acknowledged(code, action, payload, timeout):
        assert code == "CP01"
        assert action == "Reset"
        assert payload == {"type": "Soft"}
        return {"status": "Accepted"}

    monkeypatch.setattr(manager, "send_call", acknowledged)
    
    resp = client.post("/api/charge_points/CP01/reset", json={"type": "Soft"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "Accepted"
    assert "Reset" in resp.json()["message"]

@pytest.fixture(scope="function", autouse=True)
def apply_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

def test_reset_rejected(monkeypatch):
    class MockRole:
        def __init__(self, name):
            self.name = name
    class MockUser:
        def __init__(self, id, roles):
            self.id = id
            self.email = "admin@test.com"
            self.full_name = "Admin"
            self.roles = [MockRole(r) for r in roles]
            
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])
    db = SessionLocalTest()
    point = db.query(ChargePoint).filter_by(code="CP01").one()
    point.status = "online"
    point.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.close()
    monkeypatch.setitem(manager.active_connections, "CP01", mock.AsyncMock())
    
    async def rejected(code, action, payload, timeout):
        return {"status": "Rejected"}

    monkeypatch.setattr(manager, "send_call", rejected)
    
    resp = client.post("/api/charge_points/CP01/reset", json={"type": "Hard"})
    assert resp.status_code == 502
    assert "chấp nhận" in resp.json()["detail"] or "chấp nhận" in resp.json()["detail"].lower() or "chấp nhận" in resp.text

def test_reset_timeout(monkeypatch):
    import asyncio
    class MockRole:
        def __init__(self, name):
            self.name = name
    class MockUser:
        def __init__(self, id, roles):
            self.id = id
            self.email = "admin@test.com"
            self.full_name = "Admin"
            self.roles = [MockRole(r) for r in roles]
            
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])
    db = SessionLocalTest()
    point = db.query(ChargePoint).filter_by(code="CP01").one()
    point.status = "online"
    point.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.close()
    monkeypatch.setitem(manager.active_connections, "CP01", mock.AsyncMock())
    
    async def timeout_call(code, action, payload, timeout):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(manager, "send_call", timeout_call)
    
    resp = client.post("/api/charge_points/CP01/reset", json={"type": "Soft"})
    assert resp.status_code == 504
    assert "thời gian" in resp.text

def test_reset_disconnect(monkeypatch):
    class MockRole:
        def __init__(self, name):
            self.name = name
    class MockUser:
        def __init__(self, id, roles):
            self.id = id
            self.email = "admin@test.com"
            self.full_name = "Admin"
            self.roles = [MockRole(r) for r in roles]
            
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])
    db = SessionLocalTest()
    point = db.query(ChargePoint).filter_by(code="CP01").one()
    point.status = "online"
    point.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.close()
    monkeypatch.setitem(manager.active_connections, "CP01", mock.AsyncMock())
    
    async def disconnect_call(code, action, payload, timeout):
        raise ConnectionError()

    monkeypatch.setattr(manager, "send_call", disconnect_call)
    
    resp = client.post("/api/charge_points/CP01/reset", json={"type": "Soft"})
    assert resp.status_code == 409
    assert "ngắt kết nối" in resp.text

def test_reset_ocpp_error(monkeypatch):
    from app.services.ocpp_parser import OCPPError
    class MockRole:
        def __init__(self, name):
            self.name = name
    class MockUser:
        def __init__(self, id, roles):
            self.id = id
            self.email = "admin@test.com"
            self.full_name = "Admin"
            self.roles = [MockRole(r) for r in roles]
            
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])
    db = SessionLocalTest()
    point = db.query(ChargePoint).filter_by(code="CP01").one()
    point.status = "online"
    point.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.close()
    monkeypatch.setitem(manager.active_connections, "CP01", mock.AsyncMock())
    
    async def ocpp_error_call(code, action, payload, timeout):
        raise OCPPError("msg_id", "NotSupported", "Error desc", {})

    monkeypatch.setattr(manager, "send_call", ocpp_error_call)
    
    resp = client.post("/api/charge_points/CP01/reset", json={"type": "Soft"})
    assert resp.status_code == 502
    assert "từ chối" in resp.text
