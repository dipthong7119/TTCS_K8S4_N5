import pytest
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, pack_call_result, pack_call_error, parse_message
from datetime import datetime, timezone, timedelta
from app.models.user import User
from app.models.charge_point import ChargePoint, Connector
from app.models.station import Station
from app.models.connector_error import ConnectorError
from app.models.ocpp_message import OcppMessage
from app.models.id_tag import IdTag
from app.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    # Tao dummy user, station and charge point
    user = User(id=1, email="test@test.com", password_hash="123", full_name="Test User")
    station = Station(id=1, name="Test Station", owner_id=1, status="active")
    cp = ChargePoint(id=1, code="CP001", station_id=1, status="offline")
    db.add(user)
    db.add(station)
    db.add(cp)
    db.commit()
    
    yield db
    
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_handle_invalid_json(db_session):
    resp = handle_ocpp_message(db_session, "CP001", "invalid json")
    msg_type, msg_id, _, err_code, err_desc, _ = parse_message(resp)
    assert msg_type == 4
    assert err_code in ["FormationViolation", "ProtocolError"]

def test_handle_boot_notification(db_session):
    raw_msg = pack_call("msg1", "BootNotification", {"chargePointVendor": "V", "chargePointModel": "M", "firmwareVersion": "1.0"})
    resp = handle_ocpp_message(db_session, "CP001", raw_msg)
    
    msg_type, msg_id, _, payload, _, _ = parse_message(resp)
    assert msg_type == 3
    assert msg_id == "msg1"
    assert payload["status"] == "Accepted"
    
    cp = db_session.query(ChargePoint).filter_by(code="CP001").first()
    assert cp.status == "online"
    assert cp.vendor == "V"
    assert cp.model == "M"
    assert cp.firmware_version == "1.0"
    assert cp.last_seen_at is not None

def test_handle_boot_notification_inactive_station(db_session):
    station = db_session.query(Station).first()
    station.status = "inactive"
    db_session.commit()
    
    raw_msg = pack_call("msg2", "BootNotification", {})
    resp = handle_ocpp_message(db_session, "CP001", raw_msg)
    
    msg_type, msg_id, _, payload, _, _ = parse_message(resp)
    assert payload["status"] == "Rejected"
    
    cp = db_session.query(ChargePoint).filter_by(code="CP001").first()
    assert cp.status == "offline" # Giữ nguyên

def test_handle_heartbeat(db_session):
    raw_msg = pack_call("msg3", "Heartbeat", {})
    resp = handle_ocpp_message(db_session, "CP001", raw_msg)
    
    msg_type, msg_id, _, payload, _, _ = parse_message(resp)
    assert msg_type == 3
    assert msg_id == "msg3"
    assert "currentTime" in payload
    
    cp = db_session.query(ChargePoint).filter_by(code="CP001").first()
    assert cp.last_seen_at is not None

def test_handle_unsupported_action(db_session):
    raw_msg = pack_call("msg4", "UnknownAction", {})
    resp = handle_ocpp_message(db_session, "CP001", raw_msg)
    
    msg_type, msg_id, _, err_code, err_desc, _ = parse_message(resp)
    assert msg_type == 4
    assert msg_id == "msg4"
    assert err_code == "NotImplemented"

def test_handle_status_notification(db_session):
    # Setup connector
    cp = db_session.query(ChargePoint).filter_by(code="CP001").first()
    conn = Connector(charge_point_id=cp.id, connector_id=1, status="rảnh")
    db_session.add(conn)
    db_session.commit()
    
    raw_msg = pack_call("msg5", "StatusNotification", {
        "connectorId": 1,
        "status": "Charging",
        "errorCode": "NoError"
    })
    
    resp = handle_ocpp_message(db_session, "CP001", raw_msg)
    msg_type, msg_id, _, payload, _, _ = parse_message(resp)
    assert msg_type == 3
    assert msg_id == "msg5"
    
    # Check connector status
    conn_db = db_session.query(Connector).filter_by(id=conn.id).first()
    assert conn_db.status == "bận"
    
def test_handle_status_notification_error(db_session):
    # Setup connector
    cp = db_session.query(ChargePoint).filter_by(code="CP001").first()
    conn = Connector(charge_point_id=cp.id, connector_id=1, status="rảnh")
    db_session.add(conn)
    db_session.commit()
    
    raw_msg = pack_call("msg6", "StatusNotification", {
        "connectorId": 1,
        "status": "Faulted",
        "errorCode": "InternalError",
        "info": "Something broke"
    })
    
    handle_ocpp_message(db_session, "CP001", raw_msg)
    
    conn_db = db_session.query(Connector).filter_by(id=conn.id).first()
    assert conn_db.status == "lỗi"
    assert conn_db.error_code == "InternalError"
    
    # Check error table
    err = db_session.query(ConnectorError).filter_by(connector_id=conn.id).first()
    assert err is not None
    assert err.error_code == "InternalError"
    assert err.info == "Something broke"

def test_handle_status_notification_unregistered_connector(db_session):
    raw_msg = pack_call("msg7", "StatusNotification", {
        "connectorId": 99,
        "status": "Available",
        "errorCode": "NoError"
    })
    
    resp = handle_ocpp_message(db_session, "CP001", raw_msg)
    
    cp = db_session.query(ChargePoint).filter_by(code="CP001").first()
    conn = db_session.query(Connector).filter_by(charge_point_id=cp.id, connector_id=99).first()
    assert conn is None

from app.models.id_tag import IdTag

def test_handle_authorize(db_session):
    now = datetime.now(timezone.utc)
    tag1 = IdTag(id_tag="VALID1", user_id=1, is_blocked=False, expiry_date=now + timedelta(days=1))
    tag2 = IdTag(id_tag="BLOCKED1", user_id=1, is_blocked=True)
    tag3 = IdTag(id_tag="EXPIRED1", user_id=1, is_blocked=False, expiry_date=now - timedelta(days=1))
    
    db_session.add_all([tag1, tag2, tag3])
    db_session.commit()
    
    # Valid
    raw1 = pack_call("msg_a1", "Authorize", {"idTag": "VALID1"})
    resp1 = handle_ocpp_message(db_session, "CP001", raw1)
    msg_type, msg_id, _, payload, _, _ = parse_message(resp1)
    assert payload["idTagInfo"]["status"] == "Accepted"
    
    # Blocked
    raw2 = pack_call("msg_a2", "Authorize", {"idTag": "BLOCKED1"})
    resp2 = handle_ocpp_message(db_session, "CP001", raw2)
    msg_type, msg_id, _, payload, _, _ = parse_message(resp2)
    assert payload["idTagInfo"]["status"] == "Blocked"
    
    # Expired
    raw3 = pack_call("msg_a3", "Authorize", {"idTag": "EXPIRED1"})
    resp3 = handle_ocpp_message(db_session, "CP001", raw3)
    msg_type, msg_id, _, payload, _, _ = parse_message(resp3)
    assert payload["idTagInfo"]["status"] == "Expired"
    
    # Invalid
    raw4 = pack_call("msg_a4", "Authorize", {"idTag": "UNKNOWN"})
    resp4 = handle_ocpp_message(db_session, "CP001", raw4)
    msg_type, msg_id, _, payload, _, _ = parse_message(resp4)
    assert payload["idTagInfo"]["status"] == "Invalid"
