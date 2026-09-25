from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.models.user import User
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

WRONG_CREDENTIALS = "email ho\u1eb7c m\u1eadt kh\u1ea9u kh\u00f4ng \u0111\u00fang"
ACCOUNT_LOCKED = "t\u00e0i kho\u1ea3n t\u1ea1m kho\u00e1 15 ph\u00fat"
PASSWORD = "ValidPassword123!"


def test_wrong_email_and_password_return_same_generic_error(
    client: TestClient,
    user_factory: Callable[..., User],
) -> None:
    user_factory(password=PASSWORD)

    wrong_password = client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "wrong-password"},
    )
    unknown_email = client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_wrong_credentials_message_matches_specification(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "wrong-password"},
    )

    assert response.json() == {"detail": WRONG_CREDENTIALS}


def test_sixth_attempt_is_locked_for_fifteen_minutes(
    client: TestClient,
    db_session: Session,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(password=PASSWORD)
    payload = {"email": user.email, "password": "wrong-password"}
    wrong_response = None

    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        response = client.post("/auth/login", json=payload)
        assert response.status_code == 401
        if wrong_response is None:
            wrong_response = response.json()
        assert response.json() == wrong_response

    db_session.refresh(user)
    assert user.failed_login_count == settings.MAX_LOGIN_ATTEMPTS
    assert user.locked_until is not None
    now = datetime.now(UTC).replace(tzinfo=None)
    assert now + timedelta(minutes=14, seconds=50) <= user.locked_until
    assert user.locked_until <= now + timedelta(minutes=15, seconds=10)

    locked_response = client.post(
        "/auth/login",
        json={"email": user.email, "password": PASSWORD},
    )
    assert locked_response.status_code == 401
    assert locked_response.json() != wrong_response


def test_locked_message_matches_specification(
    client: TestClient,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(password=PASSWORD)
    wrong_payload = {"email": user.email, "password": "wrong-password"}
    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        client.post("/auth/login", json=wrong_payload)

    response = client.post(
        "/auth/login",
        json={"email": user.email, "password": PASSWORD},
    )

    assert response.json() == {"detail": ACCOUNT_LOCKED}


def test_lock_survives_new_client(
    client: TestClient,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(password=PASSWORD)
    wrong_payload = {"email": user.email, "password": "wrong-password"}
    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        client.post("/auth/login", json=wrong_payload)

    client.close()
    restarted_client = TestClient(client.app)
    try:
        response = restarted_client.post(
            "/auth/login",
            json={"email": user.email, "password": PASSWORD},
        )
    finally:
        restarted_client.close()

    assert response.status_code == 401


def test_repeated_failures_from_same_ip_are_rate_limited(client: TestClient) -> None:
    for attempt in range(settings.MAX_LOGIN_ATTEMPTS):
        response = client.post(
            "/auth/login",
            json={
                "email": f"missing-{attempt}@example.com",
                "password": "wrong-password",
            },
        )
        assert response.status_code == 401

    blocked_response = client.post(
        "/auth/login",
        json={"email": "another-missing@example.com", "password": "wrong-password"},
    )

    assert blocked_response.status_code == 401
    assert blocked_response.json() == {"detail": ACCOUNT_LOCKED}


def test_successful_login_sets_httponly_cookie_and_resets_failures(
    client: TestClient,
    db_session: Session,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(password=PASSWORD)
    wrong_payload = {"email": user.email, "password": "wrong-password"}
    client.post("/auth/login", json=wrong_payload)

    response = client.post(
        "/auth/login",
        json={"email": user.email, "password": PASSWORD},
    )

    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert response.json()["roles"] == ["station_owner"]
    db_session.refresh(user)
    assert user.failed_login_count == 0
    assert user.locked_until is None
    assert user.last_failed_ip is None
