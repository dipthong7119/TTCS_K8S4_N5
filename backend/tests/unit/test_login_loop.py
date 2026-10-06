from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.database import get_db
from app.main import app
from app.models.user import Role, User


def test_login_10_times(db_session) -> None:
    role = db_session.query(Role).filter(Role.name == "admin").first()
    if role is None:
        role = Role(name="admin")
        db_session.add(role)
    user = User(
        email="loop-test@example.com",
        password_hash=hash_password("ValidPassword123!"),
        full_name="Loop Test",
        roles=[role],
    )
    db_session.add(user)
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        for _ in range(10):
            response = client.post(
                "/api/auth/login",
                json={"email": user.email, "password": "ValidPassword123!"},
            )
            assert response.status_code == 200, response.text
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)
