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

def test_duplicate_connection(caplog):
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
        
        with caplog.at_level("INFO", logger="app.services.connection_manager"):
            await manager.connect("CP01", ws2)
        assert manager.active_connections["CP01"] == ws2
        
        # ws1 should be closed
        ws1.close.assert_called_once_with(code=1000, reason="New connection opened")
        assert "code=CP01" in caplog.text
        assert f"old_connection_id={id(ws1)}" in caplog.text
        assert f"new_connection_id={id(ws2)}" in caplog.text
        
        # Test old socket disconnect does not remove new socket
        manager.disconnect("CP01", ws1)
        assert manager.active_connections.get("CP01") == ws2
        
        manager.disconnect("CP01", ws2)
        assert "CP01" not in manager.active_connections

    asyncio.run(run_test())

@pytest.fixture(scope="function", autouse=True)
def apply_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

def test_connection_manager_fails_pending_on_disconnect():
    from unittest.mock import AsyncMock

    from app.services.connection_manager import ConnectionManager
    manager = ConnectionManager()
    websocket = AsyncMock()

    async def exercise():
        await manager.connect("CP-1", websocket)
        pending = asyncio.create_task(
            manager.send_call("CP-1", "Reset", {"type": "Soft"}, timeout=1)
        )
        await asyncio.sleep(0)  # let send_call start
        manager.disconnect("CP-1", websocket)
        
        with pytest.raises(ConnectionError, match="Charge point disconnected"):
            await pending

    asyncio.run(exercise())

def test_connection_manager_fails_pending_on_reconnect():
    from unittest.mock import AsyncMock

    from app.services.connection_manager import ConnectionManager
    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    async def exercise():
        await manager.connect("CP-1", ws1)
        pending = asyncio.create_task(
            manager.send_call("CP-1", "Reset", {"type": "Soft"}, timeout=1)
        )
        await asyncio.sleep(0)  # let send_call start
        await manager.connect("CP-1", ws2)
        
        with pytest.raises(ConnectionError, match="Charge point reconnected"):
            await pending

    asyncio.run(exercise())

def test_connection_manager_resolves_call_error():
    import json
    from unittest.mock import AsyncMock

    from app.services.connection_manager import ConnectionManager
    from app.services.ocpp_parser import OCPPError
    manager = ConnectionManager()
    websocket = AsyncMock()

    async def exercise():
        await manager.connect("CP-1", websocket)
        pending = asyncio.create_task(
            manager.send_call("CP-1", "Reset", {"type": "Soft"}, timeout=1)
        )
        await asyncio.sleep(0)
        frame = json.loads(websocket.send_text.await_args.args[0])
        msg_id = frame[1]
        await manager.resolve_call_error("CP-1", msg_id, "NotSupported", "Reset not supported", {})
        
        with pytest.raises(OCPPError) as exc_info:
            await pending
        assert exc_info.value.error_code == "NotSupported"
        assert exc_info.value.message_id == msg_id

    asyncio.run(exercise())

def test_connection_manager_ignores_callresult_from_wrong_websocket():
    import json
    from unittest.mock import AsyncMock

    from app.services.connection_manager import ConnectionManager
    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    async def exercise():
        await manager.connect("CP-1", ws1)
        pending = asyncio.create_task(
            manager.send_call("CP-1", "Reset", {"type": "Soft"}, timeout=1)
        )
        await asyncio.sleep(0)
        frame = json.loads(ws1.send_text.await_args.args[0])
        msg_id = frame[1]
        
        # Try to resolve with wrong websocket
        matched = await manager.resolve_call_result("CP-1", msg_id, {"status": "Accepted"}, websocket=ws2)
        assert matched is False
        assert not manager.pending_calls[("CP-1", msg_id)].done()
        
        # Resolve with correct websocket
        matched = await manager.resolve_call_result("CP-1", msg_id, {"status": "Accepted"}, websocket=ws1)
        assert matched is True
        
        result = await pending
        assert result == {"status": "Accepted"}

    asyncio.run(exercise())
