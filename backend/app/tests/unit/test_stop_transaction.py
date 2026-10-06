"""Test cases cho handler StopTransaction (SCRUM-163 / T-38)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.id_tag import IdTag
from app.models.orphan_message import OrphanMessage
from app.models.station import Station
from app.models.user import Role, User
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, parse_message


@pytest.fixture()
def db_session():
    """Tạo DB in-memory cho test StopTransaction."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    driver_role = Role(id=1, name="driver")
    driver = User(id=1, email="driver@test.com", password_hash="x", full_name="Valid Driver", is_active=True)
    driver.roles = [driver_role]
    db.add(driver)
    
    station = Station(id=1, name="Station 1", owner_id=1, status="active")
    db.add(station)
    
    point = ChargePoint(id=1, code="CP001", station_id=1, status="online")
    db.add(point)
    
    connector = Connector(id=1, charge_point_id=1, connector_id=1, status="charging")
    db.add(connector)
    
    valid_tag = IdTag(id=1, id_tag="VALID-TAG", user_id=1, is_blocked=False)
    db.add(valid_tag)

    # Thêm một ChargingSession đang active để StopTransaction dừng
    session = ChargingSession(
        id=1,
        charge_point_id=1,
        charge_point_code="CP001",
        station_id=1,
        station_name="Station 1",
        connector_number=1,
        user_id=1,
        driver_name="Valid Driver",
        id_tag_id=1,
        id_tag="VALID-TAG",
        meter_start_wh=1000,
        started_at=datetime.now(UTC) - timedelta(hours=1),
        ended_at=None,
        status="active"
    )
    db.add(session)

    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_stop_transaction_valid(db_session):
    """Ca 1: Kết thúc phiên hợp lệ -> cập nhật phiên, trả Accepted."""
    end_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "transactionId": 1,
        "meterStop": 2000,
        "timestamp": end_time,
        "reason": "Local"
    }
    raw_call = pack_call("msg1", "StopTransaction", payload)
    
    raw_response = handle_ocpp_message(db_session, "CP001", raw_call)
    msg_type, msg_id, _, payload_resp, _, _ = parse_message(raw_response)
    
    assert msg_type == 3
    assert msg_id == "msg1"
    assert payload_resp["idTagInfo"]["status"] == "Accepted"
    
    session = db_session.query(ChargingSession).get(1)
    assert session.meter_stop_wh == 2000
    assert session.ended_at is not None
    assert session.stop_reason == "Local"
    assert session.status == "completed"
    
    # Kiểm tra trạng thái connector trở về available
    conn = db_session.query(Connector).filter_by(connector_id=1).first()
    assert conn.status == "available"


def test_stop_transaction_invalid_transaction_id(db_session):
    """Ca 2: transactionId không tồn tại -> lưu vào orphan_messages, trả về {}."""
    end_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "transactionId": 999,
        "meterStop": 2000,
        "timestamp": end_time,
        "reason": "Local",
        "transactionData": []
    }
    raw_call = pack_call("msg2", "StopTransaction", payload)
    
    raw_response = handle_ocpp_message(db_session, "CP001", raw_call)
    msg_type, msg_id, _, payload_resp, _, _ = parse_message(raw_response)
    
    assert msg_type == 3
    assert msg_id == "msg2"
    assert payload_resp == {}  # Empty result as defined in _dispatch fallback
    
    orphan = db_session.query(OrphanMessage).filter_by(transaction_id=999).first()
    assert orphan is not None
    assert orphan.action == "StopTransaction"
    assert orphan.reason == "transaction_not_found"


def test_stop_transaction_idempotency(db_session):
    """Ca 3: Trụ gửi lại StopTransaction cùng mã tin nhắn -> idempotent, trả Accepted."""
    end_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "transactionId": 1,
        "meterStop": 2000,
        "timestamp": end_time,
        "reason": "Local"
    }
    raw_call = pack_call("msg_dup", "StopTransaction", payload)
    
    # Gửi lần 1
    raw_resp1 = handle_ocpp_message(db_session, "CP001", raw_call)
    
    # Gửi lần 2
    raw_resp2 = handle_ocpp_message(db_session, "CP001", raw_call)
    
    assert raw_resp1 == raw_resp2
    session = db_session.query(ChargingSession).get(1)
    assert session.meter_stop_wh == 2000


def test_stop_transaction_already_ended(db_session):
    """Ca 4: Trụ gửi StopTransaction cho phiên đã đóng (transactionId đúng nhưng tin nhắn mới) -> trả Accepted, không lỗi."""
    # Đóng phiên trước
    session = db_session.query(ChargingSession).get(1)
    session.ended_at = datetime.now(UTC)
    session.meter_stop_wh = 1500
    db_session.commit()
    
    end_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "transactionId": 1,
        "meterStop": 2000,
        "timestamp": end_time,
        "reason": "Local"
    }
    raw_call = pack_call("msg3", "StopTransaction", payload)
    
    raw_response = handle_ocpp_message(db_session, "CP001", raw_call)
    _, _, _, payload_resp, _, _ = parse_message(raw_response)
    
    assert payload_resp["idTagInfo"]["status"] == "Accepted"
    
    # Không đổi meter_stop_wh
    session = db_session.query(ChargingSession).get(1)
    assert session.meter_stop_wh == 1500


def test_stop_transaction_validation_errors(db_session):
    """Bắt lỗi dữ liệu không hợp lệ (FormationViolation)."""
    # transactionId âm
    payload = {"transactionId": -1, "meterStop": 2000, "timestamp": datetime.now(UTC).isoformat()}
    resp = handle_ocpp_message(db_session, "CP001", pack_call("m1", "StopTransaction", payload))
    assert parse_message(resp)[3] == "FormationViolation"
    
    # meterStop âm
    payload = {"transactionId": 1, "meterStop": -5, "timestamp": datetime.now(UTC).isoformat()}
    resp = handle_ocpp_message(db_session, "CP001", pack_call("m2", "StopTransaction", payload))
    assert parse_message(resp)[3] == "FormationViolation"
    
    # Thiếu timestamp
    payload = {"transactionId": 1, "meterStop": 2000}
    resp = handle_ocpp_message(db_session, "CP001", pack_call("m3", "StopTransaction", payload))
    assert parse_message(resp)[3] == "FormationViolation"
    
    # transactionData không phải array
    payload = {"transactionId": 1, "meterStop": 2000, "timestamp": datetime.now(UTC).isoformat(), "transactionData": {}}
    resp = handle_ocpp_message(db_session, "CP001", pack_call("m4", "StopTransaction", payload))
    assert parse_message(resp)[3] == "FormationViolation"
