import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from app.services.jobs import check_offline_charge_points
from app.database import Base, engine, SessionLocal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.models.user import User
from app.models.station import Station
from app.models.charge_point import ChargePoint
from app.models.connector_error import ConnectorError

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
async def test_check_offline_charge_points(db_session):
    # Setup data: 1 online (recent), 1 online (old), 1 offline
    now = datetime.now(timezone.utc)
    cp1 = ChargePoint(code="CP01", station_id=1, status="online", last_seen_at=now - timedelta(minutes=5))
    cp2 = ChargePoint(code="CP02", station_id=1, status="online", last_seen_at=now - timedelta(minutes=15))
    cp3 = ChargePoint(code="CP03", station_id=1, status="offline", last_seen_at=now - timedelta(minutes=20))
    db_session.add_all([cp1, cp2, cp3])
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

