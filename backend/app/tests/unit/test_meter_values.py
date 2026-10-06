import datetime
import time
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.charging_session import ChargingSession
from app.models.meter_value import MeterValue
from app.services.meter_values import get_latest_meter_value


def create_dummy_session(db: Session) -> ChargingSession:
    """Tạo một phiên sạc giả để test khoá ngoại."""
    session = ChargingSession(
        charge_point_code="CP_TEST",
        station_name="Test Station",
        connector_number=1,
        meter_start_wh=0,
        started_at=datetime.datetime.now(datetime.timezone.utc),
        status="active",
    )
    db.add(session)
    db.commit()
    return session


def test_constraints_and_unit(db: Session):
    """Test ràng buộc NOT NULL, khoá ngoại và lưu unit nguyên văn."""
    # SQLite PRAGMA for testing foreign keys
    db.execute(sa.text("PRAGMA foreign_keys = ON"))
    
    # 1. Foreign key constraint
    with pytest.raises(IntegrityError):
        invalid_mv = MeterValue(
            session_id=9999,  # Không tồn tại
            measured_at=datetime.datetime.now(datetime.timezone.utc),
            measurand="Energy.Active.Import.Register",
            value=100.5,
        )
        db.add(invalid_mv)
        db.commit()
    db.rollback()

    session = create_dummy_session(db)

    # 2. Missing NOT NULL fields
    with pytest.raises(IntegrityError):
        invalid_mv = MeterValue(
            session_id=session.id,
            # Thiếu measured_at
            measurand="Power.Active.Import",
            value=50.0,
        )
        db.add(invalid_mv)
        db.commit()
    db.rollback()

    # 3. Insert valid row with unit "kWh" (nguyên văn)
    valid_mv = MeterValue(
        session_id=session.id,
        measured_at=datetime.datetime.now(datetime.timezone.utc),
        measurand="Energy.Active.Import.Register",
        value=Decimal("123.456"),
        unit="kWh"
    )
    db.add(valid_mv)
    db.commit()

    # Verify unit is stored and read back exactly as "kWh"
    db.refresh(valid_mv)
    assert valid_mv.unit == "kWh"
    assert valid_mv.value == Decimal("123.456")


def test_get_latest_meter_value(db: Session):
    """Test truy vấn lấy số đo mới nhất."""
    session1 = create_dummy_session(db)
    session2 = create_dummy_session(db)

    # Thêm số đo cho session1
    mv1 = MeterValue(
        session_id=session1.id,
        measured_at=datetime.datetime(2023, 1, 1, 10, 0, 0, tzinfo=datetime.timezone.utc),
        measurand="Energy",
        value=10,
    )
    mv2 = MeterValue(
        session_id=session1.id,
        measured_at=datetime.datetime(2023, 1, 1, 10, 0, 20, tzinfo=datetime.timezone.utc),
        measurand="Energy",
        value=30,
    )
    mv3 = MeterValue(
        session_id=session1.id,
        measured_at=datetime.datetime(2023, 1, 1, 10, 0, 10, tzinfo=datetime.timezone.utc),
        measurand="Energy",
        value=20,
    )
    
    # Thêm số đo cho session2 (để đảm bảo không lẫn dữ liệu)
    mv_other = MeterValue(
        session_id=session2.id,
        measured_at=datetime.datetime(2023, 1, 1, 10, 0, 30, tzinfo=datetime.timezone.utc),
        measurand="Energy",
        value=100,
    )

    db.add_all([mv1, mv2, mv3, mv_other])
    db.commit()

    # Truy vấn số đo mới nhất của session1
    latest = get_latest_meter_value(db, session1.id, "Energy")
    assert latest is not None
    assert latest.value == 30  # Ứng với measured_at lớn nhất (10:00:20)
    
    # Truy vấn cho measurand không tồn tại
    assert get_latest_meter_value(db, session1.id, "Power") is None


def test_index_usage_explain_query_plan(db: Session):
    """Chứng minh truy vấn sử dụng chỉ mục bằng EXPLAIN QUERY PLAN trên SQLite."""
    # Bỏ qua nếu không dùng SQLite
    if db.bind.dialect.name != "sqlite":
        pytest.skip("Test chỉ dành cho SQLite")

    session = create_dummy_session(db)
    
    query = (
        sa.select(MeterValue)
        .where(MeterValue.session_id == session.id, MeterValue.measurand == "Energy")
        .order_by(MeterValue.measured_at.desc())
        .limit(1)
    )
    
    # Chạy EXPLAIN QUERY PLAN
    explain_sql = f"EXPLAIN QUERY PLAN {query.compile(compile_kwargs={'literal_binds': True})}"
    result = db.execute(sa.text(explain_sql)).fetchall()
    
    plan_text = " ".join([str(row) for row in result]).lower()
    # Phải có nhắc đến chỉ mục vừa tạo (ix_meter_values_session_id_measured_at)
    assert "ix_meter_values_session_id_measured_at" in plan_text


def test_performance_light_load(db: Session):
    """Test tải nhẹ: chèn khoảng 10.000 dòng và đo thời gian truy vấn (< 50ms)."""
    session = create_dummy_session(db)
    
    # Bulk insert 10,000 dòng
    now = datetime.datetime.now(datetime.timezone.utc)
    meter_values = []
    for i in range(10000):
        meter_values.append(
            MeterValue(
                session_id=session.id,
                measured_at=now + datetime.timedelta(seconds=i),
                measurand="Energy",
                value=i,
            )
        )
    db.bulk_save_objects(meter_values)
    db.commit()
    
    # Đo thời gian truy vấn
    start_time = time.time()
    latest = get_latest_meter_value(db, session.id, "Energy")
    end_time = time.time()
    
    duration_ms = (end_time - start_time) * 1000
    assert latest.value == 9999
    assert duration_ms < 50, f"Truy vấn quá chậm: {duration_ms}ms"


def test_migration_upgrade_downgrade(tmp_path, monkeypatch):
    from pathlib import Path

    from alembic.config import Config

    from alembic import command
    from app.config import settings

    db_url = f"sqlite:///{(tmp_path / 'test_migration.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)

    cfg = Config()
    cfg.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parents[3] / "alembic"),
    )
    cfg.set_main_option("sqlalchemy.url", db_url)

    engine = sa.create_engine(db_url)
    try:
        command.upgrade(cfg, "head")
        inspector = sa.inspect(engine)
        assert "meter_values" in inspector.get_table_names()
        indexes = {idx["name"] for idx in inspector.get_indexes("meter_values")}
        assert "ix_meter_values_session_id_measured_at" in indexes

        command.downgrade(cfg, "h20261004_defaults")
        inspector = sa.inspect(engine)
        assert "meter_values" in inspector.get_table_names()
        indexes = {idx["name"] for idx in inspector.get_indexes("meter_values")}
        assert "ix_meter_values_session_measured" in indexes

        command.upgrade(cfg, "head")
        inspector = sa.inspect(engine)
        indexes = {idx["name"] for idx in inspector.get_indexes("meter_values")}
        assert "ix_meter_values_session_id_measured_at" in indexes
    finally:
        engine.dispose()