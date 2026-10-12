"""Unit tests for SCRUM-59 (S-25, T-53, T-54): Phiên không có tin kết thúc quá lâu bị đánh dấu bất thường."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import app.models.ocpp_message  # noqa: F401
import app.models.orphan_message  # noqa: F401
from app.core.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.models.user import User
from app.services.jobs import review_stale_sessions_once


class MockRole:
    def __init__(self, name: str):
        self.name = name


class MockUser:
    def __init__(self, user_id: int, roles: list[str]):
        self.id = user_id
        self.email = "operator@test.com"
        self.full_name = "Operator Test"
        self.roles = [MockRole(r) for r in roles]


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["operator"])
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_data(db):
    owner = User(id=1, email="owner@test.com", password_hash="123", full_name="Station Owner")
    station = Station(id=1, name="Station 1", owner_id=1, status="active")
    point_online = ChargePoint(
        id=1, code="CP01", station_id=1, status="online", last_seen_at=datetime.now(UTC)
    )
    point_offline = ChargePoint(
        id=2, code="CP02", station_id=1, status="offline", last_seen_at=datetime.now(UTC) - timedelta(hours=3)
    )
    c1 = Connector(id=1, charge_point_id=1, connector_id=1, status="charging")
    c2 = Connector(id=2, charge_point_id=1, connector_id=2, status="charging")
    c3 = Connector(id=3, charge_point_id=1, connector_id=3, status="charging")
    c4 = Connector(id=4, charge_point_id=2, connector_id=1, status="unknown")
    c5 = Connector(id=5, charge_point_id=2, connector_id=2, status="unknown")
    db.add_all([owner, station, point_online, point_offline, c1, c2, c3, c4, c5])
    db.commit()

    now = datetime.now(UTC).replace(tzinfo=None)

    # Session 1: normal active session on CP01 conn 1
    s1 = ChargingSession(
        id=101, charge_point_id=1, charge_point_code="CP01", station_id=1, station_name="Station 1",
        connector_number=1, user_id=1, driver_name="Driver 1", meter_start_wh=1000,
        started_at=now - timedelta(hours=1), status="active",
    )
    # Session 2: anomaly session due to offline charge point on CP02 conn 1
    s2 = ChargingSession(
        id=102, charge_point_id=2, charge_point_code="CP02", station_id=1, station_name="Station 1",
        connector_number=1, user_id=1, driver_name="Driver 2", meter_start_wh=1000,
        started_at=now - timedelta(hours=2), status="anomaly", anomaly_reason="offline",
    )
    # Session 3: anomaly session due to negative kWh on CP01 conn 2
    s3 = ChargingSession(
        id=103, charge_point_id=1, charge_point_code="CP01", station_id=1, station_name="Station 1",
        connector_number=2, user_id=1, driver_name="Driver 3", meter_start_wh=2000,
        started_at=now - timedelta(hours=3), status="needs_review", anomaly_reason="negative_kwh",
    )
    # Session 4: anomaly session due to remote_stop_timeout on CP01 conn 3
    s4 = ChargingSession(
        id=104, charge_point_id=1, charge_point_code="CP01", station_id=1, station_name="Station 1",
        connector_number=3, user_id=1, driver_name="Driver 4", meter_start_wh=1500,
        started_at=now - timedelta(hours=4), status="needs_review", anomaly_reason="remote_stop_timeout",
    )
    # Session 5: completed normal session
    s5 = ChargingSession(
        id=105, charge_point_id=1, charge_point_code="CP01", station_id=1, station_name="Station 1",
        connector_number=1, user_id=1, driver_name="Driver 5", meter_start_wh=1000, meter_stop_wh=5000,
        energy_kwh=4.0, started_at=now - timedelta(hours=5), ended_at=now - timedelta(hours=4),
        status="completed",
    )
    db.add_all([s1, s2, s3, s4, s5])
    db.commit()
    return {"point_online": point_online, "point_offline": point_offline}


def test_list_anomalies_requires_operator_or_admin(client):
    """NFR: Chỉ vai trò vận hành viên và quản trị mới được xem danh sách bất thường."""
    # Operator -> 200
    res = client.get("/api/sessions/anomalies")
    assert res.status_code == 200

    # Admin -> 200
    app.dependency_overrides[get_current_user] = lambda: MockUser(2, ["admin"])
    res = client.get("/api/sessions/anomalies")
    assert res.status_code == 200

    # Driver -> 403 Forbidden
    app.dependency_overrides[get_current_user] = lambda: MockUser(3, ["driver"])
    res = client.get("/api/sessions/anomalies")
    assert res.status_code == 403


def test_list_anomalies_returns_all_unresolved_anomalies(client, sample_data):
    """Danh sách hiển thị đúng các phiên có status là anomaly hoặc needs_review."""
    res = client.get("/api/sessions/anomalies")
    assert res.status_code == 200
    data = res.json()

    # Sessions 102, 103, 104 are anomalies
    assert data["total"] == 3
    ids = [item["id"] for item in data["items"]]
    assert 102 in ids
    assert 103 in ids
    assert 104 in ids
    assert 101 not in ids  # active
    assert 105 not in ids  # completed

    # Counters
    assert data["offline_count"] == 1
    assert data["negative_kwh_count"] == 1


def test_filter_anomalies_by_reason(client, sample_data):
    """Bộ lọc lý do bất thường: offline, negative_kwh, remote_stop_timeout."""
    # Filter by offline
    res_offline = client.get("/api/sessions/anomalies?reason=offline")
    assert res_offline.status_code == 200
    data_offline = res_offline.json()
    assert data_offline["total"] == 1
    assert data_offline["items"][0]["id"] == 102

    # Filter by negative_kwh
    res_neg = client.get("/api/sessions/anomalies?reason=negative_kwh")
    assert res_neg.status_code == 200
    data_neg = res_neg.json()
    assert data_neg["total"] == 1
    assert data_neg["items"][0]["id"] == 103

    # Filter by remote_stop_timeout
    res_stop = client.get("/api/sessions/anomalies?reason=remote_stop_timeout")
    assert res_stop.status_code == 200
    data_stop = res_stop.json()
    assert data_stop["total"] == 1
    assert data_stop["items"][0]["id"] == 104


def test_filter_anomalies_days_parameter(client, sample_data):
    """Kiểm tra tham số lọc thời gian và xử lý lỗi validation."""
    # Days = all
    res = client.get("/api/sessions/anomalies?days=all")
    assert res.status_code == 200
    assert res.json()["total"] == 3

    # Invalid days format -> 422
    res_bad = client.get("/api/sessions/anomalies?days=invalid")
    assert res_bad.status_code == 422

    # Days out of bounds -> 422
    res_oob = client.get("/api/sessions/anomalies?days=0")
    assert res_oob.status_code == 422


def test_job_marks_stale_session_and_appears_in_anomalies(db, client, sample_data, monkeypatch):
    """AC 1: Phiên đang sạc mà trụ ngoại tuyến quá ngưỡng -> job đánh dấu và hiện trong danh sách bất thường."""
    now = datetime.now(UTC).replace(tzinfo=None)
    monkeypatch.setattr("app.config.settings.SESSION_OFFLINE_GRACE_SECONDS", 60)
    monkeypatch.setattr("app.routers.monitoring.notify_session_change", Mock())

    # Add a new active session on an offline charge point connector 2
    point_offline = sample_data["point_offline"]
    point_offline.last_seen_at = now - timedelta(seconds=120)
    new_session = ChargingSession(
        id=106, charge_point_id=point_offline.id, charge_point_code=point_offline.code,
        station_id=1, station_name="Station 1", connector_number=2, user_id=1,
        driver_name="Stale Driver", meter_start_wh=1000, started_at=now - timedelta(hours=1),
        status="active",
    )
    db.add(new_session)
    db.commit()

    # Before job: session is active, total anomalies = 3
    res_before = client.get("/api/sessions/anomalies")
    assert res_before.json()["total"] == 3

    # Run review job
    changed_count = review_stale_sessions_once(db)
    assert changed_count >= 1

    # After job: session 106 marked anomaly, total anomalies = 4
    db.refresh(new_session)
    assert new_session.status == "anomaly"
    assert new_session.anomaly_reason == "offline"

    res_after = client.get("/api/sessions/anomalies")
    assert res_after.json()["total"] == 4
    anomaly_ids = [item["id"] for item in res_after.json()["items"]]
    assert 106 in anomaly_ids


def test_late_stop_transaction_removes_session_from_anomalies(db, client, sample_data):
    """AC 2: Phiên bất thường sau đó nhận StopTransaction muộn -> phiên đóng bình thường và rời khỏi danh sách."""
    from app.ocpp.handlers.stop_transaction import handle_stop_transaction

    anomaly_session = db.query(ChargingSession).filter_by(id=102).one()
    assert anomaly_session.status == "anomaly"

    point = sample_data["point_offline"]
    stop_payload = {
        "transactionId": anomaly_session.id,
        "meterStop": 6000,
        "timestamp": datetime.now(UTC).isoformat(),
        "reason": "EVDisconnected",
    }

    # Process StopTransaction
    response = handle_stop_transaction(db, point, "msg-late-stop", stop_payload)
    db.commit()
    assert response.startswith("[3")

    # Session is now completed
    db.refresh(anomaly_session)
    assert anomaly_session.status == "completed"
    assert anomaly_session.ended_at is not None
    assert anomaly_session.meter_stop_wh == 6000

    # Query anomaly list -> session 102 has left the list
    res = client.get("/api/sessions/anomalies")
    assert res.status_code == 200
    ids = [item["id"] for item in res.json()["items"]]
    assert 102 not in ids
