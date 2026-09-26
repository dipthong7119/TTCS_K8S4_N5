import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.connection_manager import manager
import unittest.mock as mock
from app.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.models.user import User
from app.core.deps import get_current_user

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



client = TestClient(app)

@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    db = SessionLocalTest()
    user = User(id=1, email="admin@test.com", password_hash="123", full_name="Admin")
    db.add(user)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine_test)

def test_reset_offline():
    class MockRole:
        def __init__(self, name):
            self.name = name
    class MockUser:
        def __init__(self, id, roles):
            self.id = id
            self.roles = [MockRole(r) for r in roles]
            
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])
    
    resp = client.post("/api/charge_points/CP01/reset", json={"type": "Soft"})
    assert resp.status_code == 400
    assert "ngoại tuyến" in resp.json()["detail"]

def test_reset_online():
    class MockRole:
        def __init__(self, name):
            self.name = name
    class MockUser:
        def __init__(self, id, roles):
            self.id = id
            self.roles = [MockRole(r) for r in roles]
            
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])
    
    # Mock connection
    manager.active_connections["CP01"] = mock.AsyncMock()
    
    resp = client.post("/api/charge_points/CP01/reset", json={"type": "Soft"})
    assert resp.status_code == 200
    assert "Reset" in resp.json()["message"]
    
    # Check if send_text was called
    manager.active_connections["CP01"].send_text.assert_called_once()
    
    del manager.active_connections["CP01"]

@pytest.fixture(scope="function", autouse=True)
def apply_override():
    app.dependency_overrides[get_db] = override_get_db
    try:
        main_app.dependency_overrides[get_db] = override_get_db
    except:
        pass
    yield
    app.dependency_overrides.clear()
    try:
        main_app.dependency_overrides.clear()
    except:
        pass
