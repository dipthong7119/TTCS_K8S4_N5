"""
Test cho handler Heartbeat và cơ chế cập nhật last_seen_at (SCRUM-117).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, parse_message


@pytest.fixture()
def db_session():
    """DB SQLite in-memory cho test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Tạo dữ liệu trạm và trụ
    station = Station(id=1, name="Trạm Heartbeat", owner_id=1, status="active")
    cp = ChargePoint(
        id=1,
        code="CP-HB-TEST",
        station_id=1,
        status="online",
        vendor="A",
        model="B",
        firmware_version="1.0",
        last_seen_at=None,
    )
    db.add_all([station, cp])
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


def _send_call(
    db, action: str, payload: dict, cp_code: str = "CP-HB-TEST", msg_id: str = "msg-1"
):
    raw = pack_call(msg_id, action, payload)
    resp = handle_ocpp_message(db, cp_code, raw)
    if not resp:
        return None
    msg_type, resp_id, _, result, _, _ = parse_message(resp)
    return result


def test_heartbeat_updates_last_seen_at(db_session):
    """Gửi Heartbeat: last_seen_at đổi và trả về currentTime hợp lệ."""
    cp_before = db_session.query(ChargePoint).filter_by(code="CP-HB-TEST").one()
    assert cp_before.last_seen_at is None

    result = _send_call(db_session, "Heartbeat", {})

    # Kiểm tra currentTime
    assert "currentTime" in result
    current_time_str = result["currentTime"]
    assert current_time_str.endswith("Z")

    # Kiểm tra db
    db_session.expire_all()
    cp_after = db_session.query(ChargePoint).filter_by(code="CP-HB-TEST").one()
    assert cp_after.last_seen_at is not None


def test_other_message_updates_last_seen_at(db_session):
    """Gửi tin nhắn khác (ví dụ StatusNotification): last_seen_at cũng đổi."""
    payload = {"connectorId": 1, "errorCode": "NoError", "status": "Available"}
    _send_call(db_session, "StatusNotification", payload)

    db_session.expire_all()
    cp = db_session.query(ChargePoint).filter_by(code="CP-HB-TEST").one()
    assert cp.last_seen_at is not None


def test_touch_last_seen_preserves_other_columns(db_session):
    """Hàm cập nhật chỉ động vào cột last_seen_at (các cột khác giữ nguyên)."""
    # Gửi Heartbeat để cập nhật last_seen_at
    _send_call(db_session, "Heartbeat", {})

    db_session.expire_all()
    cp = db_session.query(ChargePoint).filter_by(code="CP-HB-TEST").one()

    # vendor, model, firmware_version giữ nguyên
    assert cp.vendor == "A"
    assert cp.model == "B"
    assert cp.firmware_version == "1.0"


def test_unknown_charge_point_does_not_crash(db_session):
    """Trụ có mã không tồn tại: không làm lỗi hệ thống (bỏ qua cập nhật)."""
    raw = pack_call("unknown-heartbeat", "Heartbeat", {})
    response = handle_ocpp_message(db_session, "UNKNOWN-CP", raw)

    assert "SecurityError" in response
