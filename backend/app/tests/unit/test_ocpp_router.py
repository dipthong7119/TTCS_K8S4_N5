from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app as main_app
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

client = TestClient(main_app)

@pytest.fixture(scope="function", autouse=True)
def apply_override():
    main_app.dependency_overrides[get_db] = override_get_db
    yield
    main_app.dependency_overrides.clear()

@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    db = SessionLocalTest()
    
    user = User(id=1, email="test@test.com", password_hash="123", full_name="Test User")
    station = Station(id=1, name="Test Station", owner_id=1, status="active")
    cp = ChargePoint(id=1, code="CP_VALID", station_id=1, status="offline")
    db.add(user)
    db.add(station)
    db.add(cp)
    db.commit()
    db.close()
    
    yield
    
    Base.metadata.drop_all(bind=engine_test)

def test_websocket_accepts_valid_cp():
    with client.websocket_connect("/ocpp/CP_VALID", subprotocols=["ocpp1.6"]) as websocket:
        import json
        raw_msg = json.dumps([2, "msg1", "BootNotification", {"chargePointVendor": "V"}])
        websocket.send_text(raw_msg)
        
        data = websocket.receive_text()
        resp = json.loads(data)
        assert resp[0] == 3
        assert resp[1] == "msg1"
        assert resp[2]["status"] == "Accepted"


def test_websocket_boot_accepted_when_station_is_paused():
    db = SessionLocalTest()
    db.query(Station).filter_by(id=1).one().status = "inactive"
    db.commit()
    db.close()

    with client.websocket_connect("/ocpp/CP_VALID", subprotocols=["ocpp1.6"]) as websocket:
        websocket.send_text('[2,"paused-boot","BootNotification",{}]')
        assert __import__("json").loads(websocket.receive_text())[2]["status"] == "Accepted"


def test_websocket_boot_rejected_when_station_is_locked():
    db = SessionLocalTest()
    db.query(Station).filter_by(id=1).one().status = "locked"
    db.commit()
    db.close()

    with client.websocket_connect("/ocpp/CP_VALID", subprotocols=["ocpp1.6"]) as websocket:
        websocket.send_text('[2,"locked-boot","BootNotification",{}]')
        assert __import__("json").loads(websocket.receive_text())[2]["status"] == "Rejected"

def test_websocket_requires_boot_before_other_calls():
    with client.websocket_connect("/ocpp/CP_VALID", subprotocols=["ocpp1.6"]) as websocket:
        websocket.send_text('[2,"early-heartbeat","Heartbeat",{}]')
        rejected = __import__("json").loads(websocket.receive_text())
        assert rejected[0] == 4
        assert rejected[2] == "SecurityError"

        websocket.send_text('[2,"boot-after-reject","BootNotification",{}]')
        accepted = __import__("json").loads(websocket.receive_text())
        assert accepted[2]["status"] == "Accepted"

        websocket.send_text('[2,"heartbeat-after-boot","Heartbeat",{}]')
        heartbeat = __import__("json").loads(websocket.receive_text())
        assert heartbeat[0] == 3

def test_websocket_rejects_invalid_cp():
    from starlette.websockets import WebSocketDisconnect
    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect("/ocpp/CP_INVALID", subprotocols=["ocpp1.6"]) as websocket,
    ):
        websocket.receive_text()
    assert exc.value.code == 1008


def test_websocket_logs_unknown_charge_point_once():
    from starlette.websockets import WebSocketDisconnect

    with (
        patch.object(ocpp_router_mod.logger, "warning") as warning,
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ocpp/CP_UNKNOWN", subprotocols=["ocpp1.6"]) as websocket,
    ):
        websocket.receive_text()

    warning.assert_called_once()
    assert "CP_UNKNOWN" in warning.call_args.args[1]
    assert warning.call_args.args[2] == "testclient"


def test_malformed_call_error_does_not_close_websocket():
    with client.websocket_connect("/ocpp/CP_VALID", subprotocols=["ocpp1.6"]) as websocket:
        websocket.send_text('[2,"malformed-boot","BootNotification",[]]')
        error = __import__("json").loads(websocket.receive_text())
        assert error[0] == 4
        assert error[1] == "malformed-boot"

        websocket.send_text('[2,"valid-boot","BootNotification",{}]')
        accepted = __import__("json").loads(websocket.receive_text())
        assert accepted[2]["status"] == "Accepted"

def test_websocket_rejects_unsupported_protocol():
    from starlette.websockets import WebSocketDisconnect
    with (
        pytest.raises(WebSocketDisconnect) as exc,
        client.websocket_connect("/ocpp/CP_VALID", subprotocols=["ocpp1.5"]) as websocket,
    ):
        websocket.receive_text()
    assert exc.value.code == 1002

def test_websocket_disconnect_publishes_offline_status():
    import json

    from app.services import connection_manager
    
    with patch("app.services.ocpp_handlers.publish_charge_point_status") as mock_publish:
        with client.websocket_connect("/ocpp/CP_VALID", subprotocols=["ocpp1.6"]) as ws:
            ws.send_text(
                json.dumps(
                    [
                        2,
                        "boot1",
                        "BootNotification",
                        {
                            "chargePointVendor": "VendorX",
                            "chargePointModel": "ModelY",
                        },
                    ]
                )
            )
            # Receive response
            ws.receive_text()
            # Active connections should have CP_VALID
            assert "CP_VALID" in connection_manager.manager.active_connections
        
        # When context exits, the websocket is closed and disconnected.
        # It should have called publish_charge_point_status
        mock_publish.assert_called()
        # Verify it went offline in the DB
        db = SessionLocalTest()
        cp = db.query(ChargePoint).filter_by(code="CP_VALID").first()
        assert cp.status == "offline"
        db.close()


def test_replaced_websocket_does_not_send_inflight_response(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from starlette.websockets import WebSocketDisconnect

    from app.services.connection_manager import ConnectionManager
    from app.services.ocpp_parser import pack_call_result

    manager = ConnectionManager()
    replacement = object()
    monkeypatch.setattr(ocpp_router_mod, "manager", manager)

    class FakeWebSocket:
        def __init__(self):
            self.headers = {"sec-websocket-protocol": "ocpp1.6"}
            self.client = SimpleNamespace(host="testclient")
            self.accepted = False
            self.sent = []
            self.received = False

        async def accept(self, subprotocol=None):
            self.accepted = subprotocol == "ocpp1.6"

        async def receive_text(self):
            if not self.received:
                self.received = True
                return '[2,"race-boot","BootNotification",{}]'
            raise WebSocketDisconnect(code=1000)

        async def send_text(self, text):
            self.sent.append(text)

        async def close(self, code=1000, reason=None):
            return None

    websocket = FakeWebSocket()

    def finish_after_reconnect(db, charge_point_code, raw_message):
        manager.active_connections[charge_point_code] = replacement
        return pack_call_result("race-boot", {"status": "Accepted"})

    monkeypatch.setattr(
        ocpp_router_mod, "handle_ocpp_message", finish_after_reconnect
    )

    asyncio.run(ocpp_router_mod.ocpp_websocket_endpoint(websocket, "CP_VALID"))

    assert websocket.accepted
    assert websocket.sent == []
    assert manager.active_connections["CP_VALID"] is replacement
