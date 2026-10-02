from fastapi.testclient import TestClient


def test_health_check_matches_contract(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "message": "H\u1ec7 th\u1ed1ng \u0111ang ho\u1ea1t \u0111\u1ed9ng \u1ed5n \u0111\u1ecbnh",
    }
