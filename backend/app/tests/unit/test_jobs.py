import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint, Connector
from app.models.station import Station
from app.services.jobs import (
    check_offline_charge_points,
    expire_stale_charge_points_once,
)


@pytest.fixture(scope="function")
def db_session(monkeypatch):
    engine_test = create_engine(
        "sqlite:///:memory:", 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine_test)
    SessionLocalTest = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)
    db = SessionLocalTest()
    
    import app.services.jobs
    monkeypatch.setattr(app.services.jobs, "SessionLocal", SessionLocalTest)
    
    st1 = Station(id=1, name="Station 1", owner_id=1, status="active")
    db.add(st1)
    db.commit()
    
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine_test)

@pytest.mark.asyncio
async def test_check_offline_charge_points(db_session, monkeypatch):
    # Setup data: 1 online (recent), 1 online (old), 1 offline
    # timeout = HEARTBEAT_INTERVAL * MULTIPLIER = 300 * 2 = 600s = 10 phút
    # CP01 = 5 phút → online, CP02 = 15 phút → offline, CP03 đã offline sẵn
    from app.config import settings
    monkeypatch.setattr(settings, "OCPP_HEARTBEAT_INTERVAL_SECONDS", 300)
    monkeypatch.setattr(settings, "OCPP_HEARTBEAT_MULTIPLIER", 2)

    # Dùng naive UTC (không có tzinfo) để nhất quán với SQLite func.current_timestamp()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cp1 = ChargePoint(code="CP01", station_id=1, status="online", last_seen_at=now - timedelta(minutes=5))
    cp2 = ChargePoint(code="CP02", station_id=1, status="online", last_seen_at=now - timedelta(minutes=15))
    cp3 = ChargePoint(code="CP03", station_id=1, status="offline", last_seen_at=now - timedelta(minutes=20))
    db_session.add_all([cp1, cp2, cp3])
    db_session.commit()
    db_session.add(Connector(charge_point_id=cp2.id, connector_id=1, status="bận"))
    db_session.commit()

    # Run the job manually for 1 iteration
    import app.services.jobs
    original_sleep = asyncio.sleep
    async def mock_sleep(seconds):
        raise asyncio.CancelledError() # Stop the loop

    app.services.jobs.asyncio.sleep = mock_sleep

    try:
        await check_offline_charge_points()
    except asyncio.CancelledError:
        pass

    app.services.jobs.asyncio.sleep = original_sleep

    # Check results
    assert db_session.query(ChargePoint).filter_by(code="CP01").first().status == "online"
    assert db_session.query(ChargePoint).filter_by(code="CP02").first().status == "offline"
    assert db_session.query(ChargePoint).filter_by(code="CP03").first().status == "offline"
    assert db_session.query(Connector).filter_by(charge_point_id=cp2.id).one().status == "unknown"


def test_offline_sweep_is_idempotent_and_heartbeat_recovers_charge_point(
    db_session, monkeypatch
):
    from app.config import settings
    from app.services.ocpp_handlers import handle_ocpp_message
    from app.services.ocpp_parser import pack_call, parse_message

    monkeypatch.setattr(settings, "OCPP_HEARTBEAT_INTERVAL_SECONDS", 5)
    monkeypatch.setattr(settings, "OCPP_HEARTBEAT_MULTIPLIER", 2)
    point = ChargePoint(
        code="CP-RECOVER",
        station_id=1,
        status="online",
        last_seen_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=20),
    )
    point.connectors = [Connector(connector_id=1, status="bận")]
    db_session.add(point)
    db_session.commit()

    assert expire_stale_charge_points_once(db_session) == 1
    db_session.refresh(point)
    assert point.status == "offline"
    assert point.connectors[0].status == "unknown"
    assert expire_stale_charge_points_once(db_session) == 0

    response = handle_ocpp_message(
        db_session, point.code, pack_call("recovered-heartbeat", "Heartbeat", {})
    )
    db_session.refresh(point)
    assert parse_message(response)[0] == 3
    assert point.status == "online"
    assert point.connectors[0].status == "unknown"
