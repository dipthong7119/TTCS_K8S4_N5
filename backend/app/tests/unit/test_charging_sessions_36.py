"""T-36 (SCRUM-161) - Bảng `charging_sessions` kèm migration, mã phiên do hệ thống cấp.

AC:
  - Migration tiến và lùi được.
  - Hai phiên không thể cùng mở trên một đầu nối nhờ chỉ mục unique có điều kiện.
NFR:
  - Trạng thái phiên là enum rõ ràng: đang sạc, đã kết thúc, bất thường, cần xem xét.
  - `transactionId` là số nguyên tăng dần do CSDL cấp (S-17), không dùng thời gian.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - nạp đủ model cho Base.metadata
from app.config import settings
from app.database import Base
from app.models.charge_point import ChargePoint
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.models.user import User

BACKEND_DIR = Path(__file__).resolve().parents[3]
# Revision liền trước migration tạo bảng charging_sessions (e81f0a6b2c44).
REVISION_BEFORE_SESSIONS = "d4e9f7210b8c"
SESSION_STATUSES = ("active", "completed", "anomaly", "needs_review")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()

    session.add(User(id=1, email="owner@test.com", password_hash="x", full_name="Owner"))
    session.add(Station(id=1, name="Trạm A", owner_id=1, status="active"))
    session.add(ChargePoint(id=1, code="CP001", station_id=1, status="online"))
    session.add(ChargePoint(id=2, code="CP002", station_id=1, status="online"))
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def alembic_cfg(tmp_path, monkeypatch):
    """Cấu hình Alembic trỏ vào một file SQLite tạm, không đụng vào csms.db."""
    db_file = tmp_path / "t36_migration.db"
    url = f"sqlite:///{db_file.as_posix()}"
    # env.py đọc URL từ app.config.settings (nơi duy nhất được đọc biến môi trường).
    monkeypatch.setattr(settings, "DATABASE_URL", url)

    # Không truyền đường dẫn alembic.ini để env.py không gọi fileConfig (tránh đổi cấu hình logging).
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg, url


def _new_session(**overrides) -> ChargingSession:
    values = dict(
        charge_point_id=1,
        charge_point_code="CP001",
        station_id=1,
        station_name="Trạm A",
        connector_number=1,
        id_tag="TAG-0001",
        meter_start_wh=1000,
        started_at=datetime(2026, 10, 6, 8, 0, 0),
    )
    values.update(overrides)
    return ChargingSession(**values)


# ---------------------------------------------------------------------------
# AC1 - Migration tiến và lùi được
# ---------------------------------------------------------------------------


def test_migration_upgrade_creates_table_with_required_columns(alembic_cfg):
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    try:
        insp = inspect(engine)
        assert "charging_sessions" in insp.get_table_names()
        columns = {c["name"] for c in insp.get_columns("charging_sessions")}
        # Các trường mô tả của T-36: transactionId, đầu nối, thẻ, tài xế, số đo đầu/cuối,
        # thời điểm bắt đầu/kết thúc, trạng thái, lý do dừng.
        required = {
            "id",
            "charge_point_id",
            "connector_number",
            "id_tag",
            "id_tag_id",
            "user_id",
            "meter_start_wh",
            "meter_stop_wh",
            "started_at",
            "ended_at",
            "status",
            "stop_reason",
        }
        assert required <= columns
        assert insp.get_pk_constraint("charging_sessions")["constrained_columns"] == ["id"]
    finally:
        engine.dispose()


def test_migration_creates_partial_unique_index(alembic_cfg):
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            sql = conn.execute(
                text(
                    "SELECT sql FROM sqlite_master "
                    "WHERE type='index' AND name='uq_active_session_per_connector'"
                )
            ).scalar_one()
        normalized = " ".join(sql.upper().split())
        assert "UNIQUE" in normalized
        assert "WHERE ENDED_AT IS NULL" in normalized
    finally:
        engine.dispose()


def test_migration_downgrade_then_upgrade_again(alembic_cfg):
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")
    command.downgrade(cfg, REVISION_BEFORE_SESSIONS)

    engine = create_engine(url)
    try:
        assert "charging_sessions" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    # Tiến lại lần nữa vẫn thành công.
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    try:
        assert "charging_sessions" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_migration_enforces_partial_unique_index_at_db_level(alembic_cfg):
    """Ràng buộc nằm ở CSDL sau migration, không phụ thuộc model ORM."""
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    insert = text(
        "INSERT INTO charging_sessions "
        "(charge_point_id, charge_point_code, station_name, connector_number, "
        " meter_start_wh, started_at, ended_at, status) "
        "VALUES (99, 'CP-RAW', 'S', 1, 0, :started, :ended, :status)"
    )
    try:
        # Phiên đã đóng + một phiên đang mở trên cùng đầu nối: hợp lệ.
        with engine.begin() as conn:
            conn.execute(insert, {"started": "2026-10-06 07:00:00", "ended": "2026-10-06 07:30:00", "status": "completed"})
            conn.execute(insert, {"started": "2026-10-06 08:00:00", "ended": None, "status": "active"})
        # Phiên mở thứ hai trên cùng đầu nối: CSDL phải từ chối.
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(insert, {"started": "2026-10-06 09:00:00", "ended": None, "status": "active"})
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM charging_sessions")).scalar_one() == 2
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# AC2 - Hai phiên không thể cùng mở trên một đầu nối
# ---------------------------------------------------------------------------


def test_two_open_sessions_on_same_connector_are_rejected(db):
    db.add(_new_session())
    db.commit()

    db.add(_new_session(started_at=datetime(2026, 10, 6, 9, 0, 0)))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    assert db.query(ChargingSession).count() == 1


def test_new_session_allowed_after_previous_one_is_closed(db):
    first = _new_session()
    db.add(first)
    db.commit()

    first.ended_at = first.started_at + timedelta(minutes=30)
    first.meter_stop_wh = 6000
    first.status = "completed"
    first.stop_reason = "Local"
    db.commit()

    db.add(_new_session(started_at=datetime(2026, 10, 6, 9, 0, 0)))
    db.commit()

    open_sessions = db.query(ChargingSession).filter(ChargingSession.ended_at.is_(None)).all()
    assert len(open_sessions) == 1
    assert db.query(ChargingSession).count() == 2


def test_many_closed_sessions_on_same_connector_are_allowed(db):
    for i in range(3):
        start = datetime(2026, 10, 6, 8 + i, 0, 0)
        db.add(_new_session(started_at=start, ended_at=start + timedelta(minutes=10), status="completed"))
    db.commit()
    assert db.query(ChargingSession).count() == 3


def test_open_sessions_on_different_connectors_or_points_are_allowed(db):
    db.add(_new_session(connector_number=1))
    db.add(_new_session(connector_number=2))
    db.add(_new_session(charge_point_id=2, charge_point_code="CP002", connector_number=1))
    db.commit()
    assert db.query(ChargingSession).filter(ChargingSession.ended_at.is_(None)).count() == 3


# ---------------------------------------------------------------------------
# NFR - enum trạng thái + transactionId do CSDL cấp
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", SESSION_STATUSES)
def test_valid_session_statuses_are_accepted(db, status):
    ended = None if status == "active" else datetime(2026, 10, 6, 9, 0, 0)
    db.add(_new_session(status=status, ended_at=ended))
    db.commit()
    assert db.query(ChargingSession).one().status == status


def test_invalid_session_status_is_rejected(db):
    db.add(_new_session(status="charging"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_default_status_is_active(db):
    session = _new_session()
    db.add(session)
    db.commit()
    db.refresh(session)
    assert session.status == "active"
    assert session.ended_at is None


def test_transaction_id_is_auto_increment_integer(db):
    ids = []
    for connector in (1, 2, 3):
        session = _new_session(connector_number=connector)
        db.add(session)
        db.commit()
        ids.append(session.id)

    assert all(isinstance(i, int) for i in ids)
    assert ids == sorted(ids)
    assert len(set(ids)) == 3
