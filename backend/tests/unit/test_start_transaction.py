"""Test cases cho handler StartTransaction (SCRUM-162 / T-37)."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.id_tag import IdTag
from app.models.station import Station
from app.models.user import Role, User
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, parse_message


@pytest.fixture()
def db_session():
    """Tạo DB in-memory cho test StartTransaction."""
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
    
    connector = Connector(id=1, charge_point_id=1, connector_id=1, status="available")
    db.add(connector)
    
    valid_tag = IdTag(id=1, id_tag="VALID-TAG", user_id=1, is_blocked=False)
    blocked_tag = IdTag(id=2, id_tag="BLOCKED-TAG", user_id=1, is_blocked=True)
    db.add_all([valid_tag, blocked_tag])

    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_start_transaction_valid_tag_and_connector(db_session):
    """Ca 1: Thẻ hợp lệ và đầu nối rảnh -> tạo phiên active, lưu số đo đầu, trả Accepted."""
    start_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "connectorId": 1,
        "idTag": "VALID-TAG",
        "meterStart": 1000,
        "timestamp": start_time
    }
    raw_call = pack_call("msg1", "StartTransaction", payload)
    
    raw_response = handle_ocpp_message(db_session, "CP001", raw_call)
    msg_type, msg_id, _, payload_resp, _, _ = parse_message(raw_response)
    
    assert msg_type == 3
    assert msg_id == "msg1"
    assert "transactionId" in payload_resp
    assert payload_resp["idTagInfo"]["status"] == "Accepted"
    
    tx_id = payload_resp["transactionId"]
    session = db_session.query(ChargingSession).get(tx_id)
    assert session is not None
    assert session.status == "active"
    assert session.meter_start_wh == 1000
    assert session.ended_at is None
    assert session.anomaly_reason is None
    assert session.id_tag == "VALID-TAG"
    
    # Kiểm tra trạng thái connector (mặc dù StatusNotification sẽ set, ta có thể set sớm)
    conn = db_session.query(Connector).filter_by(connector_id=1).first()
    assert conn.status == "charging"


def test_start_transaction_invalid_tag(db_session):
    """Ca 2: Thẻ bị khoá/không tồn tại -> trả Blocked/Invalid, phiên needs_review."""
    start_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "connectorId": 1,
        "idTag": "INVALID-TAG",
        "meterStart": 1000,
        "timestamp": start_time
    }
    raw_call = pack_call("msg2", "StartTransaction", payload)
    
    raw_response = handle_ocpp_message(db_session, "CP001", raw_call)
    _, _, _, payload_resp, _, _ = parse_message(raw_response)
    
    assert payload_resp["idTagInfo"]["status"] == "Invalid"
    
    tx_id = payload_resp["transactionId"]
    session = db_session.query(ChargingSession).get(tx_id)
    assert session.status == "needs_review"
    assert session.anomaly_reason == "start_invalid"
    assert session.ended_at == session.started_at  # Session đóng ngay lập tức
    
    # Thẻ Blocked
    payload["idTag"] = "BLOCKED-TAG"
    raw_call = pack_call("msg3", "StartTransaction", payload)
    raw_response = handle_ocpp_message(db_session, "CP001", raw_call)
    _, _, _, payload_resp, _, _ = parse_message(raw_response)
    
    assert payload_resp["idTagInfo"]["status"] == "Blocked"
    tx_id = payload_resp["transactionId"]
    session = db_session.query(ChargingSession).get(tx_id)
    assert session.status == "needs_review"
    assert session.anomaly_reason == "start_blocked"


def test_start_transaction_concurrent_start(db_session):
    """Ca 3: Đầu nối có phiên chưa đóng -> đóng phiên cũ, tạo phiên mới có cảnh báo."""
    start_time1 = datetime.now(UTC)
    payload1 = {
        "connectorId": 1,
        "idTag": "VALID-TAG",
        "meterStart": 1000,
        "timestamp": start_time1.isoformat().replace("+00:00", "Z")
    }
    raw_resp1 = handle_ocpp_message(db_session, "CP001", pack_call("msg_c1", "StartTransaction", payload1))
    _, _, _, resp1, _, _ = parse_message(raw_resp1)
    tx_id1 = resp1["transactionId"]
    
    start_time2 = start_time1 + timedelta(minutes=10)
    payload2 = {
        "connectorId": 1,
        "idTag": "VALID-TAG",
        "meterStart": 1200,
        "timestamp": start_time2.isoformat().replace("+00:00", "Z")
    }
    raw_resp2 = handle_ocpp_message(db_session, "CP001", pack_call("msg_c2", "StartTransaction", payload2))
    _, _, _, resp2, _, _ = parse_message(raw_resp2)
    tx_id2 = resp2["transactionId"]
    
    # Phiên 1 bị đóng
    session1 = db_session.query(ChargingSession).get(tx_id1)
    assert session1.status == "anomaly"
    assert session1.stop_reason == "ConcurrentStart"
    assert session1.anomaly_reason == "concurrent_start"
    assert session1.ended_at is not None
    
    # Phiên 2 được tạo
    session2 = db_session.query(ChargingSession).get(tx_id2)
    assert session2.status == "active"
    assert session2.ended_at is None
    assert session1.id != session2.id


def test_start_transaction_idempotency(db_session):
    """Ca 4: Trụ gửi lại StartTransaction cùng mã tin nhắn -> trả cùng transactionId."""
    start_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "connectorId": 1,
        "idTag": "VALID-TAG",
        "meterStart": 1000,
        "timestamp": start_time
    }
    raw_call = pack_call("msg_dup", "StartTransaction", payload)
    
    # Gửi lần 1
    raw_resp1 = handle_ocpp_message(db_session, "CP001", raw_call)
    _, _, _, resp1, _, _ = parse_message(raw_resp1)
    tx_id1 = resp1["transactionId"]
    
    # Gửi lần 2
    raw_resp2 = handle_ocpp_message(db_session, "CP001", raw_call)
    _, _, _, resp2, _, _ = parse_message(raw_resp2)
    tx_id2 = resp2["transactionId"]
    
    assert tx_id1 == tx_id2
    assert raw_resp1 == raw_resp2
    
    # Đảm bảo chỉ có 1 phiên được tạo
    count = db_session.query(ChargingSession).count()
    assert count == 1


def test_start_transaction_validation_errors(db_session):
    """Bắt lỗi dữ liệu không hợp lệ (FormationViolation)."""
    # Sai connectorId
    payload = {"connectorId": -1, "idTag": "VALID-TAG", "meterStart": 1000, "timestamp": datetime.now(UTC).isoformat()}
    resp = handle_ocpp_message(db_session, "CP001", pack_call("m1", "StartTransaction", payload))
    assert parse_message(resp)[3] == "FormationViolation"
    
    # Sai meterStart
    payload = {"connectorId": 1, "idTag": "VALID-TAG", "meterStart": -5, "timestamp": datetime.now(UTC).isoformat()}
    resp = handle_ocpp_message(db_session, "CP001", pack_call("m2", "StartTransaction", payload))
    assert parse_message(resp)[3] == "FormationViolation"
    
    # Thiếu timestamp
    payload = {"connectorId": 1, "idTag": "VALID-TAG", "meterStart": 1000}
    resp = handle_ocpp_message(db_session, "CP001", pack_call("m3", "StartTransaction", payload))
    assert parse_message(resp)[3] == "FormationViolation"
