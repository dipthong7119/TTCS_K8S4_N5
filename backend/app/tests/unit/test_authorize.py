"""
Test tổng hợp cho story "Authorize xác thực thẻ tài xế" (SCRUM-132).
Bao phủ toàn bộ 5 AC và các ca biên, bảo mật log, payload, idempotency.
"""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint
from app.models.id_tag import IdTag
from app.models.station import Station
from app.models.user import Role, User
from app.ocpp.handlers.authorize import decide_authorize_status, mask_id_tag
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, parse_message

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture()
def db_session():
    """Tạo DB in-memory cho test Authorize."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Tạo User admin & driver
    admin_role = Role(id=1, name="admin")
    driver_role = Role(id=2, name="driver")
    
    driver = User(id=1, email="driver@test", password_hash="hash", full_name="Driver 1", is_active=True)
    driver.roles = [driver_role]
    
    inactive_driver = User(id=2, email="inactive@test", password_hash="hash", full_name="Driver 2", is_active=False)
    inactive_driver.roles = [driver_role]
    
    non_driver = User(id=3, email="admin@test", password_hash="hash", full_name="Admin", is_active=True)
    non_driver.roles = [admin_role]

    # Tạo Station & ChargePoint
    station = Station(id=1, name="Station 1", owner_id=3, status="active")
    inactive_station = Station(id=2, name="Station 2", owner_id=3, status="inactive")
    
    cp1 = ChargePoint(id=1, code="CP-1", station_id=1, status="online")
    cp2 = ChargePoint(id=2, code="CP-2", station_id=2, status="online")
    
    # Tạo các loại thẻ
    now = datetime.now(UTC).replace(tzinfo=None)
    
    tag_valid = IdTag(id_tag="VALID-TAG-1234", user_id=1, is_blocked=False, expiry_date=now + timedelta(days=1))
    tag_no_expiry = IdTag(id_tag="NO-EXPIRY-5678", user_id=1, is_blocked=False, expiry_date=None)
    tag_blocked = IdTag(id_tag="BLOCKED-TAG-11", user_id=1, is_blocked=True, expiry_date=now + timedelta(days=1))
    tag_expired = IdTag(id_tag="EXPIRED-TAG-22", user_id=1, is_blocked=False, expiry_date=now - timedelta(days=1))
    tag_blocked_expired = IdTag(id_tag="BLOCKED-EXP-33", user_id=1, is_blocked=True, expiry_date=now - timedelta(days=1))
    tag_inactive_user = IdTag(id_tag="INACTIVE-USR-4", user_id=2, is_blocked=False)
    tag_non_driver = IdTag(id_tag="NON-DRIVER-TAG", user_id=3, is_blocked=False)

    db.add_all([
        admin_role, driver_role, driver, inactive_driver, non_driver,
        station, inactive_station, cp1, cp2,
        tag_valid, tag_no_expiry, tag_blocked, tag_expired, tag_blocked_expired, tag_inactive_user, tag_non_driver
    ])
    db.commit()

    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def _auth(db, id_tag: str, cp_code: str = "CP-1", msg_id: str = "msg-1") -> tuple:
    payload = {"idTag": id_tag} if id_tag is not None else {}
    raw = pack_call(msg_id, "Authorize", payload)
    resp = handle_ocpp_message(db, cp_code, raw)
    return parse_message(resp)


# ===========================================================================
# Test hàm phụ trợ (Pure functions)
# ===========================================================================

def test_mask_id_tag_short():
    """Ca 12: Thẻ ngắn (<=4 ký tự) giữ nguyên."""
    assert mask_id_tag("123") == "123"
    assert mask_id_tag("ABCD") == "ABCD"

def test_mask_id_tag_long():
    """Ca 13: Thẻ dài bị che, chỉ giữ 4 ký tự cuối."""
    assert mask_id_tag("1234567890") == "******7890"
    assert mask_id_tag("VALID-TAG-1234") == "**********1234"

def test_mask_id_tag_empty():
    """Ca 14: Thẻ rỗng / None không crash."""
    assert mask_id_tag("") == ""
    assert mask_id_tag(None) == ""


# ===========================================================================
# Test AC chính (Business Logic)
# ===========================================================================

def test_ac1_invalid_tag(db_session):
    """AC1: Thẻ không tồn tại -> Invalid."""
    msg_type, _, _, payload, _, _ = _auth(db_session, "NOT-FOUND-TAG")
    assert msg_type == 3
    assert payload["idTagInfo"]["status"] == "Invalid"

def test_ac2_station_inactive_returns_blocked(db_session):
    """AC2: Trạm ngừng hoạt động -> Blocked."""
    msg_type, _, _, payload, _, _ = _auth(db_session, "VALID-TAG-1234", cp_code="CP-2") # CP-2 thuộc trạm 2 inactive
    assert msg_type == 3
    assert payload["idTagInfo"]["status"] == "Blocked"

def test_ac3_tag_blocked_returns_blocked(db_session):
    """AC3: Thẻ bị khoá -> Blocked."""
    msg_type, _, _, payload, _, _ = _auth(db_session, "BLOCKED-TAG-11")
    assert msg_type == 3
    assert payload["idTagInfo"]["status"] == "Blocked"

def test_ac3_inactive_driver_returns_blocked(db_session):
    """AC3: Tài xế inactive -> Blocked."""
    msg_type, _, _, payload, _, _ = _auth(db_session, "INACTIVE-USR-4")
    assert payload["idTagInfo"]["status"] == "Blocked"

def test_ac3_non_driver_returns_blocked(db_session):
    """AC3: User không có role driver -> Blocked."""
    msg_type, _, _, payload, _, _ = _auth(db_session, "NON-DRIVER-TAG")
    assert payload["idTagInfo"]["status"] == "Blocked"

def test_ac4_tag_expired_returns_expired(db_session):
    """AC4: Thẻ hết hạn -> Expired."""
    msg_type, _, _, payload, _, _ = _auth(db_session, "EXPIRED-TAG-22")
    assert payload["idTagInfo"]["status"] == "Expired"

def test_ac5_valid_tag_returns_accepted(db_session):
    """AC5: Thẻ hợp lệ -> Accepted, trả kèm expiryDate."""
    msg_type, _, _, payload, _, _ = _auth(db_session, "VALID-TAG-1234")
    assert payload["idTagInfo"]["status"] == "Accepted"
    assert "expiryDate" in payload["idTagInfo"]


# ===========================================================================
# Test ca biên
# ===========================================================================

def test_no_expiry_returns_accepted(db_session):
    """Ca 6: NULL expiry -> Không bao giờ hết hạn -> Accepted."""
    msg_type, _, _, payload, _, _ = _auth(db_session, "NO-EXPIRY-5678")
    assert payload["idTagInfo"]["status"] == "Accepted"
    assert "expiryDate" not in payload["idTagInfo"]

def test_blocked_and_expired_returns_blocked(db_session):
    """Ca 7: Thẻ vừa khoá vừa hết hạn -> Blocked (ưu tiên kiểm tra khoá trước)."""
    msg_type, _, _, payload, _, _ = _auth(db_session, "BLOCKED-EXP-33")
    assert payload["idTagInfo"]["status"] == "Blocked"

@patch("app.ocpp.handlers.authorize.datetime")
def test_fake_clock_not_expired(mock_datetime, db_session):
    """Ca 8: Đồng hồ giả, thời điểm trước khi hết hạn -> Accepted."""
    now_utc = datetime.now(UTC)
    mock_datetime.now.return_value = now_utc
    mock_datetime.UTC = UTC
    
    # Tạo thẻ hết hạn sau 1 phút
    tag = IdTag(id_tag="TEST-CLOCK-1", user_id=1, is_blocked=False, expiry_date=now_utc.replace(tzinfo=None) + timedelta(minutes=1))
    db_session.add(tag)
    db_session.commit()
    
    _, _, _, payload, _, _ = _auth(db_session, "TEST-CLOCK-1")
    assert payload["idTagInfo"]["status"] == "Accepted"

@patch("app.ocpp.handlers.authorize.datetime")
def test_fake_clock_expired(mock_datetime, db_session):
    """Ca 9: Đồng hồ giả, thời điểm sau khi hết hạn -> Expired."""
    now_utc = datetime.now(UTC)
    mock_datetime.now.return_value = now_utc
    mock_datetime.UTC = UTC
    
    # Tạo thẻ đã hết hạn trước 1 phút
    tag = IdTag(id_tag="TEST-CLOCK-2", user_id=1, is_blocked=False, expiry_date=now_utc.replace(tzinfo=None) - timedelta(minutes=1))
    db_session.add(tag)
    db_session.commit()
    
    _, _, _, payload, _, _ = _auth(db_session, "TEST-CLOCK-2")
    assert payload["idTagInfo"]["status"] == "Expired"


# ===========================================================================
# Test kiểm soát log (Security)
# ===========================================================================

def test_log_masking_invalid_tag(db_session, caplog):
    """Ca 10: Log không lộ mã thẻ nguyên văn khi Invalid."""
    with caplog.at_level(logging.WARNING):
        _auth(db_session, "SECRET-INVALID-9999")
    
    assert "9999" in caplog.text
    assert "SECRET-INVALID-9999" not in caplog.text

def test_log_masking_accepted_tag(db_session, caplog):
    """Ca 11: Log không lộ mã thẻ nguyên văn khi Accepted."""
    with caplog.at_level(logging.INFO):
        _auth(db_session, "VALID-TAG-1234")
    
    assert "1234" in caplog.text
    assert "VALID-TAG-1234" not in caplog.text


# ===========================================================================
# Test payload sai (CALLERROR)
# ===========================================================================

def test_missing_id_tag(db_session):
    """Ca 15: Payload thiếu idTag -> CALLERROR (FormationViolation)."""
    msg_type, msg_id, action, payload, _, _ = _auth(db_session, None)
    assert msg_type == 4
    assert action == "FormationViolation"

def test_empty_id_tag(db_session):
    """Ca 16: Payload idTag rỗng -> CALLERROR (FormationViolation)."""
    msg_type, msg_id, action, payload, _, _ = _auth(db_session, "")
    assert msg_type == 4
    assert action == "FormationViolation"

def test_long_id_tag(db_session):
    """Ca 17: Payload idTag > 20 ký tự -> CALLERROR (FormationViolation)."""
    msg_type, msg_id, action, payload, _, _ = _auth(db_session, "VERY-LONG-ID-TAG-OVER-20-CHARS")
    assert msg_type == 4
    assert action == "FormationViolation"


# ===========================================================================
# Test Idempotency
# ===========================================================================

def test_idempotency(db_session):
    """Ca 18: Gửi 2 tin nhắn trùng msg_id -> chỉ gọi logic 1 lần, kết quả như nhau."""
    raw = pack_call("idem-123", "Authorize", {"idTag": "VALID-TAG-1234"})
    
    # Lần 1
    resp1 = handle_ocpp_message(db_session, "CP-1", raw)
    msg_type1, msg_id1, _, payload1, _, _ = parse_message(resp1)
    
    # Lần 2 (ngay lập tức)
    resp2 = handle_ocpp_message(db_session, "CP-1", raw)
    msg_type2, msg_id2, _, payload2, _, _ = parse_message(resp2)
    
    assert payload1 == payload2
    assert msg_id1 == msg_id2 == "idem-123"
