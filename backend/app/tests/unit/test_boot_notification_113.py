"""
Test cho BootNotification (SCRUM-113).
"""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.ocpp.handlers.boot_notification import decide_boot_status
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, parse_message

# ---------------------------------------------------------------------------
# Test logic tĩnh: Quyết định trạng thái (decide_boot_status)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "station_status,expected_boot_status",
    [
        ("active", "Accepted"),  # Trạm hoạt động -> Accepted
        ("paused", "Accepted"),  # Trạm tạm ngừng bảo trì -> Accepted
        ("locked", "Rejected"),  # Trạm bị khoá -> Rejected
        (None, "Rejected"),  # Không có trạm -> Rejected
    ],
)
def test_decide_boot_status(station_status, expected_boot_status):
    """Quyết định status BootNotification dựa trên trạng thái trạm."""
    cp = ChargePoint(id=1, code="CP-TEST")
    station = Station(id=1, status=station_status) if station_status else None

    status = decide_boot_status(cp, station)
    assert status == expected_boot_status


# ---------------------------------------------------------------------------
# Test tích hợp Handler DB in-memory
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """DB SQLite in-memory."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Dữ liệu mẫu
    station1 = Station(id=1, name="Active Station", owner_id=1, status="active")
    cp1 = ChargePoint(id=1, code="CP-ACTIVE", station_id=1, status="offline")

    station2 = Station(id=2, name="Locked Station", owner_id=1, status="locked")
    cp2 = ChargePoint(id=2, code="CP-LOCKED", station_id=2, status="offline")

    db.add_all([station1, cp1, station2, cp2])
    db.commit()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def _send_boot(db, cp_code: str):
    raw = pack_call(
        "msg-boot",
        "BootNotification",
        {"chargePointVendor": "A", "chargePointModel": "B", "firmwareVersion": "1"},
    )
    resp = handle_ocpp_message(db, cp_code, raw)
    msg_type, resp_id, _, result, _, _ = parse_message(resp)
    return result


def test_boot_notification_accepted(db_session):
    """Trụ đăng ký hợp lệ, trạm active -> conf là Accepted, interval lấy từ cấu hình, trụ trực tuyến."""
    result = _send_boot(db_session, "CP-ACTIVE")

    assert result["status"] == "Accepted"
    assert "interval" in result
    assert result["currentTime"].endswith("Z")

    db_session.expire_all()
    cp = db_session.query(ChargePoint).filter_by(code="CP-ACTIVE").one()
    assert cp.status == "online"


def test_boot_notification_rejected(db_session):
    """Trụ thuộc trạm bị khoá -> conf là Rejected, trụ không trực tuyến."""
    result = _send_boot(db_session, "CP-LOCKED")

    assert result["status"] == "Rejected"
    assert "interval" in result  # Đặc tả yêu cầu vẫn có interval khi Rejected

    db_session.expire_all()
    cp = db_session.query(ChargePoint).filter_by(code="CP-LOCKED").one()
    assert cp.status == "offline"  # Không chuyển sang online


@patch("app.ocpp.handlers.boot_notification.settings")
def test_boot_notification_custom_interval(mock_settings, db_session):
    """Đổi HEARTBEAT_INTERVAL thì interval trong conf đổi theo."""
    mock_settings.HEARTBEAT_INTERVAL = 999

    result = _send_boot(db_session, "CP-ACTIVE")
    assert result["interval"] == 999


# ---------------------------------------------------------------------------
# Test logic chặn tin nhắn khi chưa Accepted (router/middleware)
# ---------------------------------------------------------------------------
# Do middleware nằm ở WebSocket Router, ta có thể test trực tiếp logic
# của hàm ocpp_websocket_endpoint hoặc mô phỏng nó theo đặc tả.
# Trong `routers/ocpp.py` đã có đoạn check `boot_accepted`.
# Gửi tin nhắn khác trước khi BootNotification Accepted -> SecurityError.
# Gửi BootNotification Rejected rồi gửi cái khác -> SecurityError.
# Gửi BootNotification Rejected rồi trạm mở khoá -> gửi lại BootNotification -> Accepted.
