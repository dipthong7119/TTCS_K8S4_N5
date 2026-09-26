import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.charge_point import ChargePoint
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


import app.routers.ocpp as ocpp_router_mod

ocpp_router_mod.SessionLocal = SessionLocalTest

client = TestClient(app)

@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    db = SessionLocalTest()
    user = User(id=1, email="test@test.com", password_hash="123", full_name="Test User")
    station = Station(id=1, name="Test Station", owner_id=1, status="active")
    cp = ChargePoint(id=1, code="CP_DUP", station_id=1, status="offline")
    db.add_all([user, station, cp])
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine_test)

def test_duplicate_connection():
    # Unfortunately, starlette TestClient's websocket_connect is synchronous blocking.
    # It's hard to open two websockets concurrently in the same test thread.
    # But we can unit test ConnectionManager directly.
    from unittest import mock

    from app.services.connection_manager import ConnectionManager
    
    manager = ConnectionManager()
    
    async def run_test():
        ws1 = mock.AsyncMock()
        ws2 = mock.AsyncMock()
        
        await manager.connect("CP01", ws1)
        assert manager.active_connections["CP01"] == ws1
        
        await manager.connect("CP01", ws2)
        assert manager.active_connections["CP01"] == ws2
        
        # ws1 should be closed
        ws1.close.assert_called_once_with(code=1000, reason="New connection opened")
        
        manager.disconnect("CP01", ws2)
        assert "CP01" not in manager.active_connections

    asyncio.run(run_test())

@pytest.fixture(scope="function", autouse=True)
def apply_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
