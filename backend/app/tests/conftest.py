import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def db(db_session):
    return db_session


@pytest.fixture()
def dummy_charge_point(db):
    from app.models.charge_point import ChargePoint
    from app.models.station import Station
    from app.models.user import User

    owner = User(
        email="meter-owner@test.local",
        password_hash="test-only",
        full_name="Test Owner",
    )
    db.add(owner)
    db.flush()

    station = Station(
        name="Test Station",
        owner_id=owner.id,
        status="active",
    )
    db.add(station)
    db.flush()

    point = ChargePoint(
        code="CP_METER_TEST",
        station_id=station.id,
        status="online",
    )
    db.add(point)
    db.commit()
    return point 