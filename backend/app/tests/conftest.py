"""
app/tests/conftest.py -- Fixtures dung chung cho toan bo test suite (T-07)
Tham chieu: SPRINT_1.md T-07, pytest docs

Fixtures:
  - db_session : SQLAlchemy session tren SQLite in-memory (rollback sau moi test)
  - client     : TestClient cua FastAPI voi session db duoc override
  - owner_a / owner_b / station_a / station_b : du lieu co dinh cho test T-07
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.user import User, Role, user_roles
from app.models.station import Station

# ---------------------------------------------------------------------------
# Co so du lieu in-memory rieng biet cho test -- khong anh huong production DB
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # dam bao 1 connection duy nhat cho SQLite :memory:
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Tao schema moi va tra ve Session.
    Sau moi test: rollback + drop tat ca bang (isolation hoan toan).
    """
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session: Session):
    """
    TestClient FastAPI voi dependency get_db duoc override sang db_session.
    Session middleware dung ItsDangerous voi secret key co dinh trong test.
    """
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper tao user + vai tro station_owner
# ---------------------------------------------------------------------------

def _make_station_owner(db: Session, email: str, full_name: str) -> User:
    """Tao User voi vai tro station_owner, password_hash co dinh (argon2id qua core/security)."""
    from app.core.security import hash_password
    hashed = hash_password("TestPass123!")

    role = db.query(Role).filter(Role.name == "station_owner").first()
    if not role:
        role = Role(name="station_owner")
        db.add(role)
        db.flush()

    user = User(
        email=email,
        password_hash=hashed,
        full_name=full_name,
        is_active=True,
    )
    db.add(user)
    db.flush()
    user.roles.append(role)
    db.commit()
    db.refresh(user)
    return user


def _make_station(db: Session, owner: User, name: str) -> Station:
    """Tao Station thuoc owner."""
    from datetime import datetime
    now = datetime.utcnow()
    station = Station(
        name=name,
        address=f"Dia chi {name}",
        owner_id=owner.id,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


@pytest.fixture(scope="function")
def two_owners_with_stations(db_session: Session):
    """
    Tra ve (owner_a, station_a, owner_b, station_b).
    Dung cho test T-07: truy cap cheo 403.
    """
    owner_a = _make_station_owner(db_session, "ownerA@example.com", "Owner A")
    owner_b = _make_station_owner(db_session, "ownerB@example.com", "Owner B")
    station_a = _make_station(db_session, owner_a, "Tram A")
    station_b = _make_station(db_session, owner_b, "Tram B")
    return owner_a, station_a, owner_b, station_b
