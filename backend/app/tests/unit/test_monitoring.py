import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User
from app.models.station import Station
from app.models.charge_point import ChargePoint, Connector
from app.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

engine_test = create_engine(
    "sqlite:///:memory:", 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
SessionLocalTest = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

def override_get_db():
    try:
        db = SessionLocalTest()
        yield db
    finally:
        db.close()




@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    db = SessionLocalTest()
    
    # 2 users: admin and station_owner
    admin = User(id=1, email="admin@test.com", password_hash="123", full_name="Admin")
    owner = User(id=2, email="owner@test.com", password_hash="123", full_name="Owner")
    db.add_all([admin, owner])
    
    # 2 stations
    st1 = Station(id=1, name="Station 1", owner_id=1, status="active")
    st2 = Station(id=2, name="Station 2", owner_id=2, status="active")
    db.add_all([st1, st2])
    
    # Charge points
    cp1 = ChargePoint(id=1, code="CP001", station_id=1, status="online")
    cp2 = ChargePoint(id=2, code="CP002", station_id=2, status="offline")
    db.add_all([cp1, cp2])
    
    # Connectors
    cn1 = Connector(id=1, charge_point_id=1, connector_id=1, status="rảnh")
    cn2 = Connector(id=2, charge_point_id=2, connector_id=1, status="bận")
    db.add_all([cn1, cn2])
    
    db.commit()
    db.close()
    
    yield
    Base.metadata.drop_all(bind=engine_test)

def test_monitoring_tree_admin():
    from app.core.deps import get_current_user

    class MockRole:
        def __init__(self, name):
            self.name = name

    class MockUser:
        def __init__(self, id, roles):
            self.id = id
            self.roles = [MockRole(r) for r in roles]

    app.dependency_overrides[get_current_user] = lambda: MockUser(id=1, roles=["admin"])
    resp = client.get("/api/monitoring/tree")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "Station 1"
    assert data[0]["charge_points"][0]["connectors"][0]["status"] == "rảnh"

def test_monitoring_tree_owner():
    from app.core.deps import get_current_user

    class MockRole:
        def __init__(self, name):
            self.name = name

    class MockUser:
        def __init__(self, id, roles):
            self.id = id
            self.roles = [MockRole(r) for r in roles]

    app.dependency_overrides[get_current_user] = lambda: MockUser(id=2, roles=["station_owner"])
    resp = client.get("/api/monitoring/tree")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Station 2"
    assert data[0]["charge_points"][0]["connectors"][0]["status"] == "bận"

@pytest.fixture(scope="function", autouse=True)
def apply_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()

client = TestClient(app)
