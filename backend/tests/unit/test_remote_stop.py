"""Unit tests for Task T-49 (SCRUM-172): RemoteStopTransaction API and 2-minute review cutoff."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.models.user import User
from app.services.connection_manager import manager
from app.services.jobs import review_stale_sessions_once

engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocalTest = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    try:
        db = SessionLocalTest()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class MockRole:
    def __init__(self, name: str):
        self.name = name


class MockUser:
    def __init__(self, user_id: int, roles: list[str]):
        self.id = user_id
        self.email = "operator@test.com"
        self.full_name = "Operator Test"
        self.roles = [MockRole(r) for r in roles]


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    db = SessionLocalTest()
    user = User(id=1, email="operator@test.com", password_hash="123", full_name="Operator Test")
    station = Station(id=1, name="Station 1", owner_id=1, status="active")
    point = ChargePoint(
        id=1,
        code="CP01",
        station_id=1,
        status="online",
        last_seen_at=datetime.now(timezone.utc),
    )
    connector = Connector(
        id=1,
        charge_point_id=1,
        connector_id=1,
        status="charging",
    )
    session = ChargingSession(
        id=101,
        charge_point_id=1,
        charge_point_code="CP01",
        station_id=1,
        station_name="Station 1",
        connector_number=1,
        user_id=1,
        driver_name="Driver Test",
        meter_start_wh=1000,
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        status="active",
    )
    db.add_all([user, station, point, connector, session])
    db.commit()
    db.close()

    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["operator"])

    yield

    Base.metadata.drop_all(bind=engine_test)
    manager.active_connections.clear()


def test_remote_stop_accepted(monkeypatch):
    """AC 1: Trụ online, trả Accepted -> không đóng phiên, chỉ ghi nhận remote_stop_requested_at và audit log."""
    monkeypatch.setitem(manager.active_connections, "CP01", mock.AsyncMock())

    async def fake_send_call(code, action, payload, timeout):
        assert code == "CP01"
        assert action == "RemoteStopTransaction"
        assert payload == {"transactionId": 101}
        return {"status": "Accepted"}

    monkeypatch.setattr(manager, "send_call", fake_send_call)

    resp = client.post("/api/sessions/101/remote-stop")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "Accepted"
    assert "phiên sẽ đóng khi trụ báo StopTransaction" in data["message"]

    db = SessionLocalTest()
    session = db.query(ChargingSession).filter_by(id=101).one()
    # Ràng buộc cốt lõi T-49: Không tự đóng phiên khi nhận Accepted!
    assert session.ended_at is None
    assert session.status == "active"
    assert session.remote_stop_requested_at is not None

    audit = (
        db.query(AuditLog)
        .filter_by(action="remote_stop.accepted", object_id="101")
        .first()
    )
    assert audit is not None
    assert audit.details.get("outcome") == "Accepted"
    db.close()


def test_remote_stop_rejected(monkeypatch):
    """AC 2: Trụ trả Rejected -> phiên vẫn tiếp tục sạc, báo lỗi rõ cho client, ghi audit."""
    monkeypatch.setitem(manager.active_connections, "CP01", mock.AsyncMock())

    async def fake_send_call(code, action, payload, timeout):
        return {"status": "Rejected"}

    monkeypatch.setattr(manager, "send_call", fake_send_call)

    resp = client.post("/api/sessions/101/remote-stop")
    assert resp.status_code == 502
    assert "Rejected" in resp.text

    db = SessionLocalTest()
    session = db.query(ChargingSession).filter_by(id=101).one()
    assert session.ended_at is None
    assert session.status == "active"
    assert session.remote_stop_requested_at is None

    audit = (
        db.query(AuditLog)
        .filter_by(action="remote_stop.rejected", object_id="101")
        .first()
    )
    assert audit is not None
    db.close()


def test_remote_stop_offline_charge_point(monkeypatch):
    """AC 3: Trụ ngoại tuyến -> báo lỗi ngay (HTTP 409), không treo kết nối, phiên không đổi."""
    db = SessionLocalTest()
    point = db.query(ChargePoint).filter_by(code="CP01").one()
    point.status = "offline"
    db.commit()
    db.close()

    resp = client.post("/api/sessions/101/remote-stop")
    assert resp.status_code == 409
    assert "ngoại tuyến" in resp.text

    db = SessionLocalTest()
    session = db.query(ChargingSession).filter_by(id=101).one()
    assert session.ended_at is None
    assert session.status == "active"
    assert session.remote_stop_requested_at is None
    db.close()


def test_remote_stop_session_already_ended():
    """Phiên đã kết thúc -> báo lỗi 409, không gửi lệnh."""
    db = SessionLocalTest()
    session = db.query(ChargingSession).filter_by(id=101).one()
    session.ended_at = datetime.now(timezone.utc).replace(tzinfo=None)
    session.status = "completed"
    db.commit()
    db.close()

    resp = client.post("/api/sessions/101/remote-stop")
    assert resp.status_code == 409
    assert "đã kết thúc" in resp.text


def test_remote_stop_not_found():
    """Phiên sạc không tồn tại -> báo lỗi 404."""
    resp = client.post("/api/sessions/9999/remote-stop")
    assert resp.status_code == 404
    assert "Không tìm thấy" in resp.text


def test_remote_stop_timeout(monkeypatch):
    """Trụ không phản hồi trong thời gian chờ -> HTTP 504 và ghi audit log."""
    monkeypatch.setitem(manager.active_connections, "CP01", mock.AsyncMock())

    async def fake_timeout(code, action, payload, timeout):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(manager, "send_call", fake_timeout)

    resp = client.post("/api/sessions/101/remote-stop")
    assert resp.status_code == 504
    assert "thời gian chờ" in resp.text

    db = SessionLocalTest()
    audit = (
        db.query(AuditLog)
        .filter_by(action="remote_stop.failed", object_id="101")
        .first()
    )
    assert audit is not None
    assert audit.details.get("outcome") == "timeout"
    db.close()


def test_remote_stop_disconnect(monkeypatch):
    """Trụ ngắt kết nối trước khi nhận lệnh -> HTTP 409 và ghi audit log."""
    monkeypatch.setitem(manager.active_connections, "CP01", mock.AsyncMock())

    async def fake_disconnect(code, action, payload, timeout):
        raise ConnectionError()

    monkeypatch.setattr(manager, "send_call", fake_disconnect)

    resp = client.post("/api/sessions/101/remote-stop")
    assert resp.status_code == 409
    assert "ngắt kết nối" in resp.text

    db = SessionLocalTest()
    audit = (
        db.query(AuditLog)
        .filter_by(action="remote_stop.failed", object_id="101")
        .first()
    )
    assert audit is not None
    assert audit.details.get("outcome") == "disconnected"
    db.close()


def test_remote_stop_forbidden_role():
    """Chỉ admin và operator mới có quyền dừng phiên từ xa (NFR)."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["driver"])
    resp = client.post("/api/sessions/101/remote-stop")
    assert resp.status_code == 403


def test_remote_stop_stale_job_review():
    """T-49 & T-53: Nếu trụ nhận Accepted nhưng quá 2 phút không gửi StopTransaction -> job đánh dấu needs_review."""
    db = SessionLocalTest()
    session = db.query(ChargingSession).filter_by(id=101).one()
    # Giả lập thời điểm yêu cầu dừng là 125 giây trước (vượt ngưỡng 120 giây của REMOTE_STOP_REVIEW_SECONDS)
    now = datetime.now(UTC).replace(tzinfo=None)
    session.remote_stop_requested_at = now - timedelta(seconds=125)
    db.commit()

    # Chạy job quét phiên bất thường một lần
    count = review_stale_sessions_once(db)
    assert count >= 1

    db.refresh(session)
    assert session.status == "needs_review"
    assert session.anomaly_reason == "remote_stop_timeout"
    db.close()
