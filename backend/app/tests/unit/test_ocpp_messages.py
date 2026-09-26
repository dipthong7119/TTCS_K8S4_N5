import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from app.services.jobs import cleanup_old_ocpp_messages
from app.database import Base, engine, SessionLocal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.models.ocpp_message import OcppMessage
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
    
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine_test)

@pytest.mark.asyncio
async def test_cleanup_old_ocpp_messages(db_session):
    now = datetime.now(timezone.utc)
    m1 = OcppMessage(msg_id="1", charge_point_code="C", action="A", response_payload={}, created_at=now - timedelta(days=1))
    m2 = OcppMessage(msg_id="2", charge_point_code="C", action="A", response_payload={}, created_at=now - timedelta(days=8))
    
    db_session.add_all([m1, m2])
    db_session.commit()
    
    import app.services.jobs
    original_sleep = asyncio.sleep
    async def mock_sleep(seconds):
        raise asyncio.CancelledError()
    app.services.jobs.asyncio.sleep = mock_sleep
    
    try:
        await cleanup_old_ocpp_messages()
    except asyncio.CancelledError:
        pass
        
    app.services.jobs.asyncio.sleep = original_sleep
    
    assert db_session.query(OcppMessage).count() == 1
    assert db_session.query(OcppMessage).first().msg_id == "1"

def test_idempotency(db_session):
    # Call handle_ocpp_message twice with same msg_id
    from app.services.ocpp_handlers import handle_ocpp_message
    from app.services.ocpp_parser import pack_call
    from app.models.charge_point import ChargePoint
    from app.models.station import Station
    
    st = Station(id=1, name="S", owner_id=1, status="active")
    cp = ChargePoint(code="CP01", station_id=1, status="offline")
    db_session.add_all([st, cp])
    db_session.commit()
    
    raw = pack_call("dup1", "Heartbeat", {})
    resp1 = handle_ocpp_message(db_session, "CP01", raw)
    resp2 = handle_ocpp_message(db_session, "CP01", raw)
    
    assert resp1 == resp2
    assert db_session.query(OcppMessage).filter_by(msg_id="dup1").count() == 1
