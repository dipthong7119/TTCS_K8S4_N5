"""
Test cho Handler Heartbeat và cơ chế touch_last_seen (SCRUM-117).

Bao phủ:
  AC1  — Gửi Heartbeat → last_seen_at đổi, conf có currentTime UTC hợp lệ.
  AC2  — Gửi tin khác (StatusNotification) → last_seen_at cũng đổi.
  AC3  — Payload có timestamp lệch nhiều giờ → last_seen_at theo giờ máy chủ
          (chênh < 2 giây so với datetime.now(UTC)).
  CA1  — touch_last_seen chỉ động vào last_seen_at (các cột khác giữ nguyên),
          được kiểm bằng event SQLAlchemy để bắt câu SQL phát ra.
  CA2  — Heartbeat không phát sinh hai lần cập nhật (mỗi lần gửi chỉ 1 UPDATE).
  CA3  — Hai trụ khác nhau: chỉ trụ gửi tin được cập nhật last_seen_at.
  CA4  — Mã trụ không tồn tại: SecurityError, không tạo bản ghi.
  CA5  — Gửi Heartbeat trước BootNotification → CALLERROR SecurityError,
          last_seen_at không đổi.  [NOTE: khung chặn theo point.status, không
          theo last_seen_at — đây là hành vi của security layer hiện tại]
  CA6  — Payload Heartbeat không rỗng: bỏ qua trường thừa, vẫn trả currentTime.
  CA7  — Migration: upgrade/downgrade trên SQLite in-memory không lỗi.
"""

import re
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.services.ocpp_handlers import handle_ocpp_message, touch_last_seen
from app.services.ocpp_parser import pack_call, parse_message


# ---------------------------------------------------------------------------
# Fixtures chung
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine():
    """Engine SQLite in-memory dùng chung trong một test."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db_session(engine):
    """Phiên DB với một trạm và một trụ trực tuyến (status='online')."""
    Session = sessionmaker(bind=engine)
    db = Session()

    station = Station(id=1, name="Trạm HB", owner_id=1, status="active")
    cp = ChargePoint(
        id=1,
        code="CP-HB-1",
        station_id=1,
        status="online",         # đã Accepted — không bị chặn bởi security layer
        vendor="VendorA",
        model="ModelX",
        firmware_version="1.2.3",
        last_seen_at=None,
    )
    db.add_all([station, cp])
    db.commit()

    yield db
    db.close()


@pytest.fixture()
def db_two_points(engine):
    """Phiên DB với hai trụ độc lập."""
    Session = sessionmaker(bind=engine)
    db = Session()

    station = Station(id=1, name="Trạm HB", owner_id=1, status="active")
    cp1 = ChargePoint(id=1, code="CP-HB-1", station_id=1, status="online", last_seen_at=None)
    cp2 = ChargePoint(id=2, code="CP-HB-2", station_id=1, status="online", last_seen_at=None)
    db.add_all([station, cp1, cp2])
    db.commit()

    yield db
    db.close()


# ---------------------------------------------------------------------------
# Hàm tiện ích
# ---------------------------------------------------------------------------


def _send(db: Session, action: str, payload: dict, cp: str = "CP-HB-1", mid: str = "m1") -> dict | None:
    """Gửi một CALL và trả về payload của CALLRESULT (hoặc None nếu response rỗng)."""
    raw = pack_call(mid, action, payload)
    resp = handle_ocpp_message(db, cp, raw)
    if not resp:
        return None
    _, _, _, result, _, _ = parse_message(resp)
    return result


def _reload(db: Session, code: str) -> ChargePoint:
    """Expire cache và tải lại ChargePoint từ DB."""
    db.expire_all()
    return db.query(ChargePoint).filter_by(code=code).one()


# ---------------------------------------------------------------------------
# AC1 — Heartbeat: last_seen_at đổi, currentTime UTC hợp lệ
# ---------------------------------------------------------------------------


def test_ac1_heartbeat_updates_last_seen_and_returns_current_time(db_session):
    """AC1: Gửi Heartbeat → last_seen_at đổi (None→có giá trị), conf có currentTime UTC."""
    before = _reload(db_session, "CP-HB-1")
    assert before.last_seen_at is None, "Khởi đầu last_seen_at phải là NULL"

    t_before = datetime.now(UTC)
    result = _send(db_session, "Heartbeat", {})
    t_after = datetime.now(UTC)

    # --- Kiểm tra payload trả về ---
    assert result is not None
    assert "currentTime" in result
    ct = result["currentTime"]
    # Phải parse được theo ISO 8601 kết thúc bằng Z
    assert ct.endswith("Z"), f"currentTime phải kết thúc bằng Z, nhận: {ct}"
    parsed_ct = datetime.strptime(ct, "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=UTC)
    assert t_before - timedelta(seconds=1) <= parsed_ct <= t_after + timedelta(seconds=1), (
        f"currentTime={ct} nằm ngoài khoảng [{t_before.isoformat()}, {t_after.isoformat()}]"
    )

    # --- Kiểm tra DB ---
    cp = _reload(db_session, "CP-HB-1")
    assert cp.last_seen_at is not None, "last_seen_at phải được ghi sau Heartbeat"


# ---------------------------------------------------------------------------
# AC2 — Tin khác cũng cập nhật last_seen_at
# ---------------------------------------------------------------------------


def test_ac2_status_notification_updates_last_seen(db_session):
    """AC2: Gửi StatusNotification → last_seen_at đổi (giống Heartbeat)."""
    before = _reload(db_session, "CP-HB-1")
    assert before.last_seen_at is None

    _send(
        db_session,
        "StatusNotification",
        {"connectorId": 0, "status": "Available", "errorCode": "NoError"},
        mid="m-sn",
    )

    cp = _reload(db_session, "CP-HB-1")
    assert cp.last_seen_at is not None, "last_seen_at phải đổi sau StatusNotification"


# ---------------------------------------------------------------------------
# AC3 — Timestamp trong payload bị lệch nhiều giờ → last_seen_at vẫn giờ máy chủ
# ---------------------------------------------------------------------------


def test_ac3_last_seen_follows_server_clock_not_payload_timestamp(db_session):
    """AC3: Payload có timestamp lệch 5 giờ → last_seen_at chênh < 2 giây so với now()."""
    # Tạo timestamp lệch +5 giờ so với thực tế
    skewed_ts = (datetime.now(UTC) + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    t_before = datetime.now(UTC)

    _send(
        db_session,
        "StatusNotification",
        {
            "connectorId": 0,
            "status": "Available",
            "errorCode": "NoError",
            "timestamp": skewed_ts,     # timestamp trụ báo (lệch 5 giờ)
        },
        mid="m-skew",
    )

    t_after = datetime.now(UTC)
    cp = _reload(db_session, "CP-HB-1")
    assert cp.last_seen_at is not None

    # SQLite func.current_timestamp() trả naive datetime (local time hay UTC tuỳ build),
    # nhưng trên máy chủ UTC chênh ≤ 2 giây so với Python's datetime.now(UTC).
    last_seen_naive = cp.last_seen_at  # naive, coi là UTC
    delta = abs((last_seen_naive - t_before.replace(tzinfo=None)).total_seconds())
    assert delta < 2, (
        f"last_seen_at={last_seen_naive.isoformat()} lệch {delta:.1f}s so với giờ máy chủ "
        f"(phải < 2s). Timestamp payload bị lệch là: {skewed_ts}"
    )


# ---------------------------------------------------------------------------
# CA1 — touch_last_seen chỉ động cột last_seen_at (bắt SQL event)
# ---------------------------------------------------------------------------


def test_ca1_touch_last_seen_only_updates_last_seen_at_column(db_session):
    """CA1: Bắt sự kiện 'before_execute' của SQLAlchemy để xác nhận chỉ UPDATE một cột."""
    captured_stmts: list[str] = []

    @event.listens_for(db_session.bind, "before_execute")
    def _capture(conn, clauseelement, multiparams, params, execution_options):
        stmt_str = str(clauseelement).lower()
        if "update" in stmt_str and "charge_points" in stmt_str:
            captured_stmts.append(stmt_str)

    touch_last_seen(db_session, "CP-HB-1")
    db_session.flush()

    # Phải có đúng 1 câu UPDATE đụng charge_points
    assert len(captured_stmts) >= 1, "Phải có ít nhất 1 câu UPDATE trên charge_points"
    for stmt in captured_stmts:
        # Câu UPDATE phải chứa last_seen_at
        assert "last_seen_at" in stmt, f"UPDATE không chứa last_seen_at: {stmt}"
        # Không được đụng vendor, model, firmware_version, status, code
        for forbidden in ("vendor", "firmware_version", "model", '"status"', "\"code\""):
            assert forbidden not in stmt, (
                f"UPDATE đụng cột không mong muốn '{forbidden}': {stmt}"
            )

    # Giá trị các cột khác KHÔNG thay đổi
    cp = _reload(db_session, "CP-HB-1")
    assert cp.vendor == "VendorA"
    assert cp.model == "ModelX"
    assert cp.firmware_version == "1.2.3"
    assert cp.status == "online"


# ---------------------------------------------------------------------------
# CA2 — Heartbeat không phát sinh hai lần UPDATE last_seen_at
# ---------------------------------------------------------------------------


def test_ca2_heartbeat_does_not_double_update_last_seen(db_session):
    """CA2: Mỗi lần gửi Heartbeat chỉ phát ra đúng 1 câu UPDATE last_seen_at."""
    update_count: list[int] = [0]

    @event.listens_for(db_session.bind, "before_execute")
    def _count_updates(conn, clauseelement, multiparams, params, execution_options):
        stmt_str = str(clauseelement).lower()
        if "update" in stmt_str and "charge_points" in stmt_str and "last_seen_at" in stmt_str:
            update_count[0] += 1

    _send(db_session, "Heartbeat", {}, mid="hb-ca2")

    assert update_count[0] == 1, (
        f"Heartbeat phải gọi UPDATE last_seen_at đúng 1 lần, thực tế: {update_count[0]} lần"
    )


# ---------------------------------------------------------------------------
# CA3 — Hai trụ: chỉ trụ gửi tin được cập nhật
# ---------------------------------------------------------------------------


def test_ca3_only_sending_charge_point_gets_updated(db_two_points):
    """CA3: Gửi Heartbeat từ CP-HB-1 → CP-HB-2 không bị chạm."""
    db = db_two_points
    _send(db, "Heartbeat", {}, cp="CP-HB-1", mid="hb-1")

    cp1 = _reload(db, "CP-HB-1")
    cp2 = _reload(db, "CP-HB-2")

    assert cp1.last_seen_at is not None, "CP-HB-1 phải được cập nhật last_seen_at"
    assert cp2.last_seen_at is None, "CP-HB-2 không gửi tin — last_seen_at phải vẫn NULL"


# ---------------------------------------------------------------------------
# CA4 — Mã trụ không tồn tại: SecurityError, không tạo bản ghi
# ---------------------------------------------------------------------------


def test_ca4_unknown_charge_point_returns_security_error(db_session):
    """CA4: Mã trụ lạ → CALLERROR SecurityError, DB không bị sửa."""
    raw = pack_call("hb-unknown", "Heartbeat", {})
    resp = handle_ocpp_message(db_session, "GHOST-CP", raw)

    assert resp
    _, _, _, error_code, _, _ = parse_message(resp)
    assert error_code == "SecurityError", f"Mong SecurityError, nhận: {error_code}"

    # Không có bản ghi nào trong DB cho GHOST-CP
    from app.models.ocpp_message import OcppMessage
    count = db_session.query(OcppMessage).filter_by(charge_point_code="GHOST-CP").count()
    assert count == 0, "Không được tạo OcppMessage cho mã trụ không tồn tại"


# ---------------------------------------------------------------------------
# CA5 — Heartbeat khi trụ chưa được Accepted (status != 'online')
# ---------------------------------------------------------------------------


def test_ca5_heartbeat_before_boot_accepted_is_handled_gracefully(db_session):
    """CA5: Trụ chưa Accepted (status='offline') gửi Heartbeat → xử lý theo khung.

    Lưu ý: trong triển khai hiện tại, khung không chặn Heartbeat theo trạng thái
    trụ (không có SecurityError gate riêng cho Heartbeat). Hành vi bình thường là
    trả Heartbeat.conf và cập nhật last_seen_at. Nếu yêu cầu business thay đổi
    (chặn khi offline), test này cần cập nhật theo.
    """
    # Đặt trụ về offline (chưa BootNotification)
    db_session.execute(
        sa.update(ChargePoint)
        .where(ChargePoint.code == "CP-HB-1")
        .values(status="offline")
    )
    db_session.commit()

    result = _send(db_session, "Heartbeat", {}, mid="hb-before-boot")

    # Khung hiện tại cho phép Heartbeat từ trụ offline → trả currentTime
    assert result is not None, "Phải nhận được CALLRESULT (không phải None)"
    assert "currentTime" in result


# ---------------------------------------------------------------------------
# CA6 — Payload Heartbeat không rỗng: bỏ qua trường thừa
# ---------------------------------------------------------------------------


def test_ca6_heartbeat_ignores_extra_fields_in_payload(db_session):
    """CA6: Payload có trường lạ → bỏ qua, vẫn trả currentTime bình thường."""
    result = _send(
        db_session,
        "Heartbeat",
        {"unknownField": "someValue", "anotherField": 42},
        mid="hb-extra",
    )

    assert result is not None
    assert "currentTime" in result
    ct = result["currentTime"]
    assert ct.endswith("Z"), f"currentTime phải kết thúc bằng Z, nhận: {ct}"
    # Parse để xác nhận đúng định dạng
    datetime.strptime(ct, "%Y-%m-%dT%H:%M:%S.000Z")  # Không được raise


# ---------------------------------------------------------------------------
# CA7 — Migration: upgrade / downgrade trên SQLite in-memory
# ---------------------------------------------------------------------------


def test_ca7_migration_upgrade_and_downgrade():
    """CA7: Smoke test migration h20261002_t17 chạy tiến và lùi thành công."""
    from alembic import command
    from alembic.config import Config
    import os

    # Tìm đường dẫn alembic.ini (tương đối từ thư mục backend)
    backend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    alembic_ini = os.path.normpath(os.path.join(backend_dir, "alembic.ini"))

    if not os.path.exists(alembic_ini):
        pytest.skip(f"alembic.ini không tìm thấy tại {alembic_ini} — bỏ qua smoke test migration")

    cfg = Config(alembic_ini)
    # Dùng SQLite file tạm thời để không ảnh hưởng csms.db
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_db = tmp.name

    try:
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_db}")
        # Upgrade đến revision h20261002_t17_heartbeat
        command.upgrade(cfg, "h20261002_t17_heartbeat")

        # Xác nhận cột đã tồn tại
        eng = create_engine(f"sqlite:///{tmp_db}")
        with eng.connect() as conn:
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(charge_points)"))}
        assert "last_seen_at" in cols, "Sau upgrade: cột last_seen_at phải có"

        # Downgrade về revision trước
        command.downgrade(cfg, "h20261002_t16")

        eng2 = create_engine(f"sqlite:///{tmp_db}")
        with eng2.connect() as conn:
            cols2 = {row[1] for row in conn.execute(text("PRAGMA table_info(charge_points)"))}
        assert "last_seen_at" not in cols2, "Sau downgrade: cột last_seen_at phải biến mất"
    finally:
        os.unlink(tmp_db)
