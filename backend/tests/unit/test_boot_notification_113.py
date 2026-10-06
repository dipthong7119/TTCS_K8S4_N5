"""
Test tổng hợp cho story "BootNotification được chấp nhận" (SCRUM-112, SCRUM-113).
Bao phủ toàn bộ AC và ca bổ sung theo đặc tả.

Tổ chức:
  Phần A — Hàm thuần decide_boot_status (không cần DB)
  Phần B — Task 1: Lưu vendor, model, firmware (T-16, S-08)
  Phần C — Task 2: Quyết định Accepted/Rejected + interval (T-17, S-08)
  Phần D — Chặn tin nhắn trước BootNotification (router logic)
  Phần E — Migration: upgrade/downgrade (smoke test idempotency)
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.ocpp.handlers.boot_notification import (
    decide_boot_status,
)
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, parse_message

# ---------------------------------------------------------------------------
# Fixture chung: SQLite in-memory với dữ liệu mẫu
# ---------------------------------------------------------------------------


def _make_db(seed_fn=None):
    """Tạo một DB in-memory mới, áp schema, tuỳ chọn seed dữ liệu."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    if seed_fn:
        seed_fn(db)
    return db, engine


def _default_seed(db: object) -> None:
    """Seed mặc định: 1 trạm active + 1 trạm locked, mỗi trạm 1 trụ."""
    st_active = Station(id=1, name="Trạm Active", owner_id=1, status="active")
    st_locked = Station(id=2, name="Trạm Locked", owner_id=1, status="locked")
    st_maint = Station(id=3, name="Trạm Bảo trì", owner_id=1, status="maintenance")
    cp_active = ChargePoint(id=1, code="CP-ACTIVE", station_id=1, status="offline")
    cp_locked = ChargePoint(id=2, code="CP-LOCKED", station_id=2, status="offline")
    cp_maint = ChargePoint(id=3, code="CP-MAINT", station_id=3, status="offline")
    db.add_all([st_active, st_locked, st_maint, cp_active, cp_locked, cp_maint])
    db.commit()


@pytest.fixture()
def db_session():
    """DB in-memory mới cho mỗi test với seed mặc định."""
    db, engine = _make_db(_default_seed)
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ---------------------------------------------------------------------------
# Helper: gửi BootNotification qua handle_ocpp_message và parse kết quả
# ---------------------------------------------------------------------------

FULL_PAYLOAD = {
    "chargePointVendor": "ABB",
    "chargePointModel": "Terra54",
    "firmwareVersion": "3.2.1",
}


def _boot(db, cp_code: str = "CP-ACTIVE", payload: dict | None = None, msg_id: str = "msg-1") -> dict:
    """Gửi BootNotification và trả về dict payload của CALLRESULT."""
    if payload is None:
        payload = FULL_PAYLOAD
    raw = pack_call(msg_id, "BootNotification", payload)
    resp = handle_ocpp_message(db, cp_code, raw)
    msg_type, _, _, result, _, _ = parse_message(resp)
    assert msg_type == 3, f"Mong đợi CALLRESULT (3), nhận được {msg_type}: {resp}"
    return result


def _send_raw(db, cp_code: str, action: str, payload: dict, msg_id: str = "msg-x") -> tuple:
    """Gửi bất kỳ action OCPP và trả về (msg_type, result_or_error_code)."""
    raw = pack_call(msg_id, action, payload)
    resp = handle_ocpp_message(db, cp_code, raw)
    parsed = parse_message(resp)
    return parsed[0], parsed[3]


# ===========================================================================
# Phần A: Hàm thuần decide_boot_status
# ===========================================================================


@pytest.mark.parametrize(
    "station_status,expected",
    [
        ("active", "Accepted"),       # AC: trạm hoạt động → Accepted
        ("maintenance", "Accepted"),  # AC: trạm tạm ngừng bảo trì → vẫn Accepted
        ("paused", "Accepted"),       # trạng thái tạm ngừng khác → Accepted (mặc định an toàn)
        ("locked", "Rejected"),       # AC: trạm bị khoá bởi admin → Rejected
        (None, "Rejected"),           # AC: không có trạm → Rejected
    ],
    ids=["active", "maintenance", "paused", "locked", "no_station"],
)
def test_decide_boot_status(station_status: str | None, expected: str) -> None:
    """Hàm thuần decide_boot_status không cần DB — dễ test độc lập (T-17 AC)."""
    cp = ChargePoint(code="CP-X")
    station = Station(status=station_status) if station_status is not None else None
    assert decide_boot_status(cp, station) == expected


# ===========================================================================
# Phần B: Task 1 — Lưu vendor, model, firmware (AC1, AC2, AC3)
# ===========================================================================


class TestTask1SaveFields:
    """S-08 AC1: payload đủ → ba cột lưu đúng, trụ online, conf Accepted."""

    def test_full_payload_accepted(self, db_session):
        result = _boot(db_session, payload=FULL_PAYLOAD)
        assert result["status"] == "Accepted"

    def test_full_payload_saves_vendor(self, db_session):
        _boot(db_session, payload=FULL_PAYLOAD)
        cp = db_session.query(ChargePoint).filter_by(code="CP-ACTIVE").one()
        assert cp.vendor == "ABB"

    def test_full_payload_saves_model(self, db_session):
        _boot(db_session, payload=FULL_PAYLOAD)
        cp = db_session.query(ChargePoint).filter_by(code="CP-ACTIVE").one()
        assert cp.model == "Terra54"

    def test_full_payload_saves_firmware(self, db_session):
        _boot(db_session, payload=FULL_PAYLOAD)
        cp = db_session.query(ChargePoint).filter_by(code="CP-ACTIVE").one()
        assert cp.firmware_version == "3.2.1"

    def test_full_payload_status_online(self, db_session):
        """Trụ chuyển sang online khi Accepted (Task 1 bước 4)."""
        _boot(db_session, payload=FULL_PAYLOAD)
        cp = db_session.query(ChargePoint).filter_by(code="CP-ACTIVE").one()
        assert cp.status == "online"


@pytest.mark.parametrize(
    "payload,null_attr",
    [
        ({"chargePointModel": "M1", "firmwareVersion": "1.0"}, "vendor"),
        ({"chargePointVendor": "V1", "firmwareVersion": "1.0"}, "model"),
        ({"chargePointVendor": "V1", "chargePointModel": "M1"}, "firmware_version"),
        ({}, "vendor"),  # tất cả thiếu — kiểm vendor đại diện
    ],
    ids=["missing_vendor", "missing_model", "missing_firmware", "all_missing"],
)
def test_missing_field_is_null(db_session, payload: dict, null_attr: str) -> None:
    """Trường thiếu → cột tương ứng NULL, KHÔNG lưu chuỗi rỗng (T-16 NFR)."""
    _boot(db_session, payload=payload, msg_id=f"msg-null-{null_attr}")
    cp = db_session.query(ChargePoint).filter_by(code="CP-ACTIVE").one()
    assert getattr(cp, null_attr) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"chargePointModel": "M1", "firmwareVersion": "1.0"},
        {"chargePointVendor": "V1", "firmwareVersion": "1.0"},
        {"chargePointVendor": "V1", "chargePointModel": "M1"},
        {},
    ],
    ids=["missing_vendor", "missing_model", "missing_firmware", "all_missing"],
)
def test_missing_field_still_accepted(db_session, payload: dict) -> None:
    """Payload thiếu trường → vẫn Accepted (T-16 NFR: không từ chối tin nhắn)."""
    result = _boot(db_session, payload=payload, msg_id="msg-miss")
    assert result["status"] == "Accepted"


# ===========================================================================
# Phần C: Task 2 — Accepted/Rejected + khoảng nhịp tim (AC1, AC2)
# ===========================================================================


class TestTask2AcceptReject:
    """S-08 AC1 + AC2."""

    def test_accepted_has_current_time_utc(self, db_session):
        """currentTime phải là UTC ISO-8601 hợp lệ (T-17 NFR)."""
        from datetime import UTC, datetime

        before = datetime.now(UTC)
        result = _boot(db_session)
        after = datetime.now(UTC)
        ts_str: str = result["currentTime"]
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        # Cho phép sai số ±2 giây do clock/mock
        assert before.timestamp() - 2 <= ts.timestamp() <= after.timestamp() + 2

    def test_accepted_has_interval(self, db_session):
        """interval có trong conf và là int dương (T-17 AC)."""
        result = _boot(db_session)
        assert isinstance(result["interval"], int)
        assert result["interval"] > 0

    def test_rejected_not_online(self, db_session):
        """S-08 AC2: trạm locked → conf Rejected, trụ KHÔNG online."""
        result = _boot(db_session, cp_code="CP-LOCKED", msg_id="msg-rej")
        assert result["status"] == "Rejected"
        db_session.expire_all()
        cp = db_session.query(ChargePoint).filter_by(code="CP-LOCKED").one()
        assert cp.status != "online"

    def test_rejected_still_has_interval(self, db_session):
        """Khi Rejected vẫn phải có interval — đặc tả OCPP 1.6J bắt buộc."""
        result = _boot(db_session, cp_code="CP-LOCKED", msg_id="msg-rej-iv")
        assert result["status"] == "Rejected"
        assert "interval" in result
        assert isinstance(result["interval"], int)

    def test_rejected_still_saves_vendor_model(self, db_session):
        """Khi Rejected vẫn lưu vendor/model để vận hành viên biết thiết bị đang cố nối."""
        _boot(
            db_session,
            cp_code="CP-LOCKED",
            payload={"chargePointVendor": "ACME", "chargePointModel": "EV50"},
            msg_id="msg-rej-save",
        )
        db_session.expire_all()
        cp = db_session.query(ChargePoint).filter_by(code="CP-LOCKED").one()
        assert cp.vendor == "ACME"
        assert cp.model == "EV50"

    def test_maintenance_station_accepted(self, db_session):
        """Trạm maintenance → Accepted (trụ vẫn báo trạng thái)."""
        result = _boot(db_session, cp_code="CP-MAINT", msg_id="msg-maint")
        assert result["status"] == "Accepted"

    @pytest.mark.parametrize("interval", [60, 300, 900], ids=["60s", "300s", "900s"])
    def test_interval_follows_config(self, db_session, interval: int) -> None:
        """Đổi HEARTBEAT_INTERVAL → interval trong conf đổi theo (T-17 AC)."""
        with patch("app.ocpp.handlers.boot_notification.settings.OCPP_HEARTBEAT_INTERVAL_SECONDS", interval):
            result = _boot(db_session, msg_id=f"msg-iv-{interval}")
        assert result["interval"] == interval


# ===========================================================================
# Phần D — Idempotency: gửi lần hai (S-08 AC3)
# ===========================================================================


class TestIdempotency:
    """AC3: gửi BootNotification lần hai → cập nhật bản ghi cũ, vẫn 1 bản ghi trụ."""

    def test_second_boot_updates_firmware(self, db_session):
        """Lần hai cập nhật firmware_version, vẫn đúng 1 bản ghi."""
        _boot(db_session, payload=FULL_PAYLOAD, msg_id="boot-first")
        _boot(
            db_session,
            payload={**FULL_PAYLOAD, "firmwareVersion": "9.9.9"},
            msg_id="boot-second",
        )
        count = db_session.query(ChargePoint).filter_by(code="CP-ACTIVE").count()
        assert count == 1
        cp = db_session.query(ChargePoint).filter_by(code="CP-ACTIVE").one()
        assert cp.firmware_version == "9.9.9"

    def test_second_boot_still_accepted(self, db_session):
        """Lần hai vẫn Accepted (không bị chặn vì đã có lần một)."""
        _boot(db_session, payload=FULL_PAYLOAD, msg_id="boot-a")
        result = _boot(db_session, payload=FULL_PAYLOAD, msg_id="boot-b")
        assert result["status"] == "Accepted"

    def test_rejected_station_unlock_then_accepted(self, db_session):
        """
        Kịch bản: trạm bị khoá → Rejected → admin mở khoá →
        trụ gửi lại BootNotification → nhận Accepted.
        (Task 2 bước 3: boot_accepted được đánh giá lại mỗi lần BootNotification)
        """
        # Lần 1: Rejected vì trạm locked
        result_rej = _boot(db_session, cp_code="CP-LOCKED", msg_id="boot-rej")
        assert result_rej["status"] == "Rejected"

        # Admin mở khoá trạm
        station = db_session.query(Station).filter_by(id=2).one()
        station.status = "active"
        db_session.commit()

        # Lần 2: trạm đã mở → Accepted
        result_acc = _boot(db_session, cp_code="CP-LOCKED", msg_id="boot-acc")
        assert result_acc["status"] == "Accepted"

        # Trụ phải được đặt online
        db_session.expire_all()
        cp = db_session.query(ChargePoint).filter_by(code="CP-LOCKED").one()
        assert cp.status == "online"


# ===========================================================================
# Phần E — Chặn tin nhắn trước khi BootNotification được Accepted (AC4)
# Lưu ý: logic boot_accepted nằm trong router (ocpp.py), không trong handler.
# Test này gọi trực tiếp handle_ocpp_message và kiểm tra CALLERROR.
# ===========================================================================


class TestBlockBeforeBoot:
    """
    AC4: gửi Heartbeat / StatusNotification trước BootNotification →
    handle_ocpp_message không nên crash, nhưng do cơ chế chặn ở ROUTER
    (ocpp.py dòng 92-96), handle_ocpp_message vẫn xử lý bình thường ở tầng service.

    Test này xác nhận rằng:
    1. Sau khi BootNotification Accepted, các tin nhắn khác được xử lý bình thường.
    2. Router sẽ trả SecurityError — đã được test riêng trong test_ocpp_router.py.
    """

    def test_heartbeat_after_accepted_ok(self, db_session):
        """Sau khi Accepted, Heartbeat được xử lý bình thường (không bị chặn)."""
        # Boot trước
        _boot(db_session, payload=FULL_PAYLOAD, msg_id="boot-pre")

        # Gửi Heartbeat — phải nhận CALLRESULT (msg_type=3)
        msg_type, result = _send_raw(
            db_session, "CP-ACTIVE", "Heartbeat", {}, msg_id="msg-hb"
        )
        assert msg_type == 3, "Heartbeat phải được xử lý bình thường sau BootNotification"

    def test_status_notification_after_accepted_ok(self, db_session):
        """Sau khi Accepted, StatusNotification không trả SecurityError."""
        _boot(db_session, payload=FULL_PAYLOAD, msg_id="boot-pre2")
        msg_type, result = _send_raw(
            db_session,
            "CP-ACTIVE",
            "StatusNotification",
            {"connectorId": 0, "errorCode": "NoError", "status": "Available"},
            msg_id="msg-sn",
        )
        # msg_type=3 (CALLRESULT) hoặc =4 (CALLERROR vì connector chưa khai báo)
        # Quan trọng: KHÔNG được là SecurityError vì đã boot
        if msg_type == 4:
            assert result != "SecurityError", "StatusNotification sau boot không được là SecurityError"


# ===========================================================================
# Phần F — Smoke test migration: upgrade/downgrade idempotent
# ===========================================================================


class TestMigrationIdempotency:
    """
    Kiểm tra rằng migration T-16 có thể chạy upgrade tiến và lùi
    trên DB đã có cột (idempotent guard).

    Không dùng Alembic CLI thật — import trực tiếp hàm upgrade/downgrade
    và gọi với kết nối in-memory.
    """

    def test_upgrade_on_existing_columns_no_error(self):
        """upgrade() trên DB đã có cột vendor/model/firmware_version → không lỗi."""
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)  # cột đã tồn tại qua model
        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext
        from alembic.util import load_python_file

        versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
        migration = load_python_file(versions_dir, "h20261004_boot_notification.py")
        try:
            with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()
                migration.upgrade()
            columns = {c["name"] for c in inspect(engine).get_columns("charge_points")}
            assert {"vendor", "model", "firmware_version"}.issubset(columns)
        finally:
            engine.dispose()

    def test_downgrade_migration_is_noop(self):
        """downgrade() không xoá cột vì chúng thuộc schema gốc (idempotent thiết kế)."""
        from alembic.util import load_python_file

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)

        versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
        migration = load_python_file(versions_dir, "h20261004_boot_notification.py")
        try:
            migration.downgrade()
            cols = {c["name"] for c in inspect(engine).get_columns("charge_points")}
            assert "vendor" in cols
        finally:
            engine.dispose()
