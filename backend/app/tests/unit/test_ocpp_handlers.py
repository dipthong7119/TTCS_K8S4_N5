from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint, Connector
from app.models.connector_error import ConnectorError
from app.models.id_tag import IdTag
from app.models.station import Station
from app.models.user import Role, User
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import (
    pack_call,
    parse_message,
)


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
    user.roles = [Role(name="driver")]
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

def test_handle_boot_notification_paused_station_still_accepts_connection(db_session):
    station = db_session.query(Station).first()
    station.status = "inactive"
    db_session.commit()
    
    raw_msg = pack_call("msg2", "BootNotification", {})
    resp = handle_ocpp_message(db_session, "CP001", raw_msg)
    
    msg_type, msg_id, _, payload, _, _ = parse_message(resp)
    assert payload["status"] == "Accepted"
    
    cp = db_session.query(ChargePoint).filter_by(code="CP001").first()
    assert cp.status == "online"


def test_handle_boot_notification_locked_station_is_rejected(db_session):
    station = db_session.query(Station).first()
    station.status = "locked"
    db_session.commit()

    response = handle_ocpp_message(
        db_session, "CP001", pack_call("msg_locked", "BootNotification", {})
    )

    assert parse_message(response)[3]["status"] == "Rejected"
    assert db_session.query(ChargePoint).filter_by(code="CP001").one().status == "offline"

def test_handle_heartbeat(db_session):
    from datetime import UTC, datetime

    before = datetime.now(UTC)
    raw_msg = pack_call("msg3", "Heartbeat", {})
    resp = handle_ocpp_message(db_session, "CP001", raw_msg)
    after = datetime.now(UTC)
    
    msg_type, msg_id, _, payload, _, _ = parse_message(resp)
    assert msg_type == 3
    assert msg_id == "msg3"
    current_time = datetime.fromisoformat(payload["currentTime"].replace("Z", "+00:00"))
    assert before.timestamp() - 1 <= current_time.timestamp() <= after.timestamp() + 1
    
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

    # Kể từ SCRUM-120, mã lỗi được lưu vào bảng connector_errors thay vì cập nhật đè lên bảng connectors
    err = db_session.query(ConnectorError).filter_by(connector_id=conn.id).first()
    assert err is not None
    assert err.error_code == "InternalError"

def test_handle_status_notification_unregistered_connector(db_session, caplog):
    raw_msg = pack_call("msg7", "StatusNotification", {
        "connectorId": 99,
        "status": "Available",
        "errorCode": "NoError"
    })
    
    with caplog.at_level("WARNING", logger="app.services.ocpp_handlers"):
        handle_ocpp_message(db_session, "CP001", raw_msg)
    
    cp = db_session.query(ChargePoint).filter_by(code="CP001").first()
    conn = db_session.query(Connector).filter_by(charge_point_id=cp.id, connector_id=99).first()
    assert conn is None
    assert "CP001" in caplog.text
    assert "99" in caplog.text


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


def test_last_seen_uses_server_clock_when_device_timestamp_is_skewed(db_session):
    charge_point = db_session.query(ChargePoint).filter_by(code="CP001").one()
    device_time = datetime.now(timezone.utc) + timedelta(hours=5)

    response = handle_ocpp_message(
        db_session,
        charge_point.code,
        pack_call(
            "clock-skew",
            "Heartbeat",
            {"timestamp": device_time.isoformat()},
        ),
    )

    database_now = db_session.query(func.current_timestamp()).scalar()
    if database_now.tzinfo is None:
        database_now = database_now.replace(tzinfo=timezone.utc)
    db_session.refresh(charge_point)
    last_seen = charge_point.last_seen_at.replace(tzinfo=timezone.utc)

    assert parse_message(response)[0] == 3
    assert abs((database_now - last_seen).total_seconds()) < 2
