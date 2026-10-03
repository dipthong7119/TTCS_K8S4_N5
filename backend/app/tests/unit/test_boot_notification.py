"""
Test cho handler BootNotification (T-16, T-17, S-08).
Tham chiếu: 02_DAC_TA_DU_AN.md — AC của S-08 và NFR của T-16/T-17.

Bốn nhóm ca kiểm thử:
  1. Payload đủ 3 trường  → 3 cột lưu đúng, trạng thái online, conf đúng chuẩn.
<<<<<<< HEAD
<<<<<<< HEAD
  2. Payload thiếu từng trường → vẫn Accepted, cột tương ứng là NULL.
  3. Gửi 2 lần (idempotency) → chỉ 1 bản ghi trụ, conf vẫn Accepted.
=======
  2. Payload thiếu từng trường → vẫn Accepted, cột tương ứng là NULL (không phải "").
  3. Gửi 2 lần (idempotency ghi đè) → chỉ 1 bản ghi trụ, conf vẫn Accepted.
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
=======
  2. Payload thiếu từng trường → vẫn Accepted, cột tương ứng là NULL (không phải "").
  3. Gửi 2 lần (idempotency ghi đè) → chỉ 1 bản ghi trụ, conf vẫn Accepted.
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
  4. Đổi OCPP_HEARTBEAT_INTERVAL_SECONDS → interval trong conf đổi theo.
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, parse_message

<<<<<<< HEAD
<<<<<<< HEAD
# ---------------------------------------------------------------------------
# Fixture: DB in-memory mới cho mỗi test, có 1 station + 1 charge point
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session():
    """DB SQLite in-memory, tạo schema đầy đủ cho mỗi test."""
=======
=======
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934

# ---------------------------------------------------------------------------
# Fixture: DB in-memory mới cho mỗi test — 1 station active + 1 trụ offline
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """DB SQLite in-memory, tạo đủ schema cho mỗi test, dọn dẹp sau."""
<<<<<<< HEAD
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
=======
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Dữ liệu tối thiểu: trạm active + trụ offline
    station = Station(id=1, name="Trạm Test", owner_id=1, status="active")
    cp = ChargePoint(id=1, code="CP-TEST", station_id=1, status="offline")
    db.add_all([station, cp])
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Helper: gửi BootNotification và parse phản hồi
# ---------------------------------------------------------------------------

<<<<<<< HEAD
<<<<<<< HEAD
def _boot(db, payload: dict, msg_id: str = "msg-boot-1"):
=======

def _boot(db, payload: dict, msg_id: str = "msg-boot-1"):
    """Đóng gói CALL, gọi handler, parse CALLRESULT trả về."""
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
=======

def _boot(db, payload: dict, msg_id: str = "msg-boot-1"):
    """Đóng gói CALL, gọi handler, parse CALLRESULT trả về."""
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
    raw = pack_call(msg_id, "BootNotification", payload)
    resp = handle_ocpp_message(db, "CP-TEST", raw)
    msg_type, resp_id, _, result, _, _ = parse_message(resp)
    return msg_type, resp_id, result


# ---------------------------------------------------------------------------
# Nhóm 1: payload đủ 3 trường
# ---------------------------------------------------------------------------

FULL_PAYLOAD = {
    "chargePointVendor": "ABB",
    "chargePointModel": "Terra54",
    "firmwareVersion": "1.2.3",
}


def test_full_payload_returns_accepted(db_session):
    """Payload đủ 3 trường → status Accepted (S-08 AC1)."""
    _, _, result = _boot(db_session, FULL_PAYLOAD)
    assert result["status"] == "Accepted"


def test_full_payload_saves_vendor_model_firmware(db_session):
<<<<<<< HEAD
<<<<<<< HEAD
    """Ba cột lưu đúng giá trị (T-16 AC)."""
=======
    """Ba cột lưu đúng giá trị từ payload (T-16 AC)."""
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
=======
    """Ba cột lưu đúng giá trị từ payload (T-16 AC)."""
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
    _boot(db_session, FULL_PAYLOAD)
    cp = db_session.query(ChargePoint).filter_by(code="CP-TEST").one()
    assert cp.vendor == "ABB"
    assert cp.model == "Terra54"
    assert cp.firmware_version == "1.2.3"


def test_full_payload_sets_status_online(db_session):
<<<<<<< HEAD
<<<<<<< HEAD
    """Trụ chuyển sang online sau BootNotification Accepted (T-16 AC)."""
=======
    """Sau khi Boot Accepted, trụ chuyển sang online (T-16 AC)."""
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
=======
    """Sau khi Boot Accepted, trụ chuyển sang online (T-16 AC)."""
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
    _boot(db_session, FULL_PAYLOAD)
    cp = db_session.query(ChargePoint).filter_by(code="CP-TEST").one()
    assert cp.status == "online"


<<<<<<< HEAD
<<<<<<< HEAD
def test_full_payload_conf_has_current_time(db_session):
=======
def test_full_payload_conf_has_current_time_utc(db_session):
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
=======
def test_full_payload_conf_has_current_time_utc(db_session):
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
    """currentTime là UTC ISO 8601 trong khoảng hợp lý (T-17 NFR)."""
    before = datetime.now(UTC)
    _, _, result = _boot(db_session, FULL_PAYLOAD)
    after = datetime.now(UTC)
    current_time = datetime.fromisoformat(result["currentTime"].replace("Z", "+00:00"))
    assert before.timestamp() - 1 <= current_time.timestamp() <= after.timestamp() + 1


<<<<<<< HEAD
<<<<<<< HEAD
def test_full_payload_conf_has_interval(db_session):
=======
def test_full_payload_conf_has_positive_interval(db_session):
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
=======
def test_full_payload_conf_has_positive_interval(db_session):
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
    """interval có trong conf và là số nguyên dương (T-17 AC)."""
    _, _, result = _boot(db_session, FULL_PAYLOAD)
    assert isinstance(result["interval"], int)
    assert result["interval"] > 0


# ---------------------------------------------------------------------------
<<<<<<< HEAD
<<<<<<< HEAD
# Nhóm 2: payload thiếu từng trường → cột tương ứng là NULL
# ---------------------------------------------------------------------------

=======
=======
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
# Nhóm 2: payload thiếu từng trường → cột tương ứng là NULL (không phải "")
# ---------------------------------------------------------------------------


<<<<<<< HEAD
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
=======
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
@pytest.mark.parametrize(
    "payload,missing_field",
    [
        (
            {"chargePointModel": "M1", "firmwareVersion": "1.0"},
            "vendor",
        ),
        (
            {"chargePointVendor": "V1", "firmwareVersion": "1.0"},
            "model",
        ),
        (
            {"chargePointVendor": "V1", "chargePointModel": "M1"},
            "firmware_version",
        ),
        (
            {},
            "vendor",  # tất cả thiếu — kiểm vendor đại diện
        ),
    ],
    ids=["missing_vendor", "missing_model", "missing_firmware", "all_missing"],
)
def test_missing_field_still_accepted(db_session, payload, missing_field):
<<<<<<< HEAD
<<<<<<< HEAD
    """Payload thiếu trường → vẫn trả Accepted (T-16 NFR: không từ chối)."""
=======
    """Payload thiếu trường vẫn trả Accepted — không từ chối (T-16 NFR)."""
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
=======
    """Payload thiếu trường vẫn trả Accepted — không từ chối (T-16 NFR)."""
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
    msg_type, _, result = _boot(db_session, payload, msg_id=f"msg-miss-{missing_field}")
    assert msg_type == 3
    assert result["status"] == "Accepted"


@pytest.mark.parametrize(
    "payload,null_attr",
    [
        (
            {"chargePointModel": "M1", "firmwareVersion": "1.0"},
            "vendor",
        ),
        (
            {"chargePointVendor": "V1", "firmwareVersion": "1.0"},
            "model",
        ),
        (
            {"chargePointVendor": "V1", "chargePointModel": "M1"},
            "firmware_version",
        ),
    ],
    ids=["null_vendor", "null_model", "null_firmware"],
)
def test_missing_field_column_is_null(db_session, payload, null_attr):
<<<<<<< HEAD
<<<<<<< HEAD
    """Cột tương ứng trường thiếu phải là NULL — không được lưu chuỗi rỗng (T-16 NFR)."""
=======
    """Cột tương ứng trường thiếu phải là NULL, không được lưu chuỗi rỗng (T-16 NFR)."""
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
=======
    """Cột tương ứng trường thiếu phải là NULL, không được lưu chuỗi rỗng (T-16 NFR)."""
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
    _boot(db_session, payload, msg_id=f"msg-null-{null_attr}")
    cp = db_session.query(ChargePoint).filter_by(code="CP-TEST").one()
    assert getattr(cp, null_attr) is None


# ---------------------------------------------------------------------------
<<<<<<< HEAD
<<<<<<< HEAD
# Nhóm 3: gửi 2 lần → vẫn chỉ 1 bản ghi trụ (idempotency từ T-30)
# ---------------------------------------------------------------------------

=======
=======
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
# Nhóm 3: gửi 2 lần → vẫn chỉ 1 bản ghi trụ (S-08 AC3)
# ---------------------------------------------------------------------------


<<<<<<< HEAD
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
=======
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
def test_second_boot_does_not_create_new_charge_point(db_session):
    """Gửi BootNotification 2 lần → bảng charge_points vẫn 1 dòng (S-08 AC3)."""
    _boot(db_session, FULL_PAYLOAD, msg_id="boot-a")
    _boot(db_session, {**FULL_PAYLOAD, "firmwareVersion": "2.0"}, msg_id="boot-b")
    count = db_session.query(ChargePoint).filter_by(code="CP-TEST").count()
    assert count == 1


def test_second_boot_still_accepted(db_session):
<<<<<<< HEAD
<<<<<<< HEAD
    """Lần gửi thứ hai vẫn trả Accepted (S-08 AC3)."""
=======
    """Lần gửi thứ hai (msg_id khác nhau) vẫn trả Accepted (S-08 AC3)."""
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
=======
    """Lần gửi thứ hai (msg_id khác nhau) vẫn trả Accepted (S-08 AC3)."""
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
    _boot(db_session, FULL_PAYLOAD, msg_id="boot-c")
    _, _, result = _boot(db_session, FULL_PAYLOAD, msg_id="boot-d")
    assert result["status"] == "Accepted"


<<<<<<< HEAD
<<<<<<< HEAD
# ---------------------------------------------------------------------------
# Nhóm 4: đổi HEARTBEAT_INTERVAL → interval trong conf đổi theo
# ---------------------------------------------------------------------------

=======
=======
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
def test_second_boot_updates_firmware_version(db_session):
    """Lần gửi thứ hai cập nhật firmware_version mà không tạo dòng mới (S-08 AC3)."""
    _boot(db_session, FULL_PAYLOAD, msg_id="boot-e")
    _boot(db_session, {**FULL_PAYLOAD, "firmwareVersion": "9.9.9"}, msg_id="boot-f")
    cp = db_session.query(ChargePoint).filter_by(code="CP-TEST").one()
    assert cp.firmware_version == "9.9.9"
    assert db_session.query(ChargePoint).count() == 1


# ---------------------------------------------------------------------------
# Nhóm 4: đổi HEARTBEAT_INTERVAL → interval trong conf đổi theo (T-17 AC)
# ---------------------------------------------------------------------------


<<<<<<< HEAD
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
=======
>>>>>>> 6a22a3bcaeb02a09abcc54b42d0a411af47de934
@pytest.mark.parametrize(
    "interval",
    [60, 300, 600],
    ids=["60s", "300s", "600s"],
)
def test_interval_follows_config(db_session, interval):
    """interval trong CALLRESULT phải bằng HEARTBEAT_INTERVAL (T-17 AC)."""
    with patch("app.ocpp.handlers.boot_notification.settings.HEARTBEAT_INTERVAL", interval):
        _, _, result = _boot(db_session, FULL_PAYLOAD, msg_id=f"boot-iv-{interval}")
    assert result["interval"] == interval
