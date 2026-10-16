"""
Unit tests cho SCRUM-90 / S-46:
Cảnh báo khi trụ ngoại tuyến quá lâu hoặc báo lỗi liên tục.
Bao phủ:
- Alert Service: phát hiện offline, phát hiện lỗi liên tục, chống trùng lặp, resolve, auto-resolve.
- Alerts Router: phân quyền (operator/admin vs driver), list alerts, summary, scan, resolve.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.charge_point import ChargePoint, Connector
from app.models.connector_error import ConnectorError
from app.models.station import Station
from app.services.alert_service import (
    auto_resolve_recovered_offline_alerts,
    get_alerts,
    resolve_alert,
    scan_connector_errors,
    scan_offline_charge_points,
)
from app.services.jobs import scan_alerts_once

# CSDL SQLite in-memory dùng chung cho unit tests
engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocalTest = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = SessionLocalTest()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


class MockRole:
    def __init__(self, name: str):
        self.name = name


class MockUser:
    def __init__(self, user_id: int, roles: list[str]):
        self.id = user_id
        self.email = f"user{user_id}@test.com"
        self.full_name = f"User {user_id}"
        self.roles = [MockRole(r) for r in roles]


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine_test)

    db = SessionLocalTest()
    # Tạo dữ liệu nền tảng
    station = Station(id=1, name="Trạm Test", owner_id=1, status="active")
    db.add(station)

    # 1. Trụ trực tuyến bình thường
    cp_online = ChargePoint(
        id=1,
        code="CP_ONLINE",
        station_id=1,
        status="online",
        last_seen_at=datetime.now(UTC).replace(tzinfo=None),
    )
    # 2. Trụ ngoại tuyến quá 20 phút (vượt ngưỡng 15 phút)
    cp_offline = ChargePoint(
        id=2,
        code="CP_OFFLINE",
        station_id=1,
        status="offline",
        last_seen_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=25),
    )
    db.add_all([cp_online, cp_offline])
    db.flush()

    # Đầu nối của trụ online
    conn1 = Connector(id=1, charge_point_id=1, connector_id=1, status="available")
    # Đầu nối của trụ offline
    conn2 = Connector(id=2, charge_point_id=2, connector_id=1, status="unknown")
    db.add_all([conn1, conn2])

    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine_test)
    app.dependency_overrides = previous_overrides


# ==============================================================================
# 1. TEST ALERT SERVICE (LOGIC NGHIỆP VỤ & CHỐNG TRÙNG)
# ==============================================================================


def test_offline_alert_triggered():
    """AC1: Trụ offline quá hạn 15 phút thì sinh một cảnh báo 'offline' trạng thái 'active'."""
    db = SessionLocalTest()
    now = datetime.now(UTC).replace(tzinfo=None)

    alerts = scan_offline_charge_points(db, now=now)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.charge_point_id == 2
    assert alert.alert_type == "offline"
    assert alert.severity == "critical"
    assert alert.status == "active"
    assert "CP_OFFLINE" in alert.message
    db.close()


def test_offline_alert_not_triggered_for_healthy_point():
    """Trụ online và có nhịp tim gần đây thì không sinh cảnh báo."""
    db = SessionLocalTest()
    now = datetime.now(UTC).replace(tzinfo=None)

    scan_offline_charge_points(db, now=now)
    cp1_alert = (
        db.query(Alert)
        .filter(Alert.charge_point_id == 1, Alert.alert_type == "offline")
        .first()
    )
    assert cp1_alert is None
    db.close()


def test_deduplication_offline_alert():
    """AC3: Cùng một trụ không tạo cảnh báo mới cho tới khi cảnh báo cũ được đóng."""
    db = SessionLocalTest()
    now = datetime.now(UTC).replace(tzinfo=None)

    # Quét lần 1 -> tạo 1 cảnh báo
    alerts1 = scan_offline_charge_points(db, now=now)
    assert len(alerts1) == 1
    db.commit()

    # Quét lần 2 ngay sau đó -> không tạo thêm cảnh báo nào
    alerts2 = scan_offline_charge_points(db, now=now + timedelta(minutes=5))
    assert len(alerts2) == 0

    total_offline_alerts = (
        db.query(Alert)
        .filter(Alert.charge_point_id == 2, Alert.alert_type == "offline")
        .count()
    )
    assert total_offline_alerts == 1
    db.close()


def test_connector_error_alert_threshold():
    """AC2: Đầu nối ghi nhận >= 3 lỗi trong 10 phút thì sinh cảnh báo connector_error."""
    db = SessionLocalTest()
    now = datetime.now(UTC).replace(tzinfo=None)

    # Thêm 3 lỗi trong vòng 5 phút gần đây
    for i in range(3):
        err = ConnectorError(
            connector_id=1,
            error_code="GroundFailure",
            occurred_at=now - timedelta(minutes=i + 1),
        )
        db.add(err)
    db.commit()

    alerts = scan_connector_errors(db, now=now)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.connector_id == 1
    assert alert.alert_type == "connector_error"
    assert alert.severity == "warning"
    assert alert.status == "active"
    assert alert.error_count == 3
    assert "CP_ONLINE" in alert.message
    db.close()


def test_connector_error_under_threshold_no_alert():
    """Chỉ có 2 lỗi (< ngưỡng 3) thì không sinh cảnh báo."""
    db = SessionLocalTest()
    now = datetime.now(UTC).replace(tzinfo=None)

    for i in range(2):
        err = ConnectorError(
            connector_id=1,
            error_code="OverCurrentFailure",
            occurred_at=now - timedelta(minutes=i + 1),
        )
        db.add(err)
    db.commit()

    alerts = scan_connector_errors(db, now=now)
    assert len(alerts) == 0
    db.close()


def test_connector_error_old_errors_ignored():
    """Lỗi xảy ra quá cửa sổ 10 phút thì không bị tính vào ngưỡng kích hoạt."""
    db = SessionLocalTest()
    now = datetime.now(UTC).replace(tzinfo=None)

    for i in range(3):
        err = ConnectorError(
            connector_id=1,
            error_code="HighTemperature",
            occurred_at=now - timedelta(minutes=15 + i),  # Quá 10 phút
        )
        db.add(err)
    db.commit()

    alerts = scan_connector_errors(db, now=now)
    assert len(alerts) == 0
    db.close()


def test_resolve_alert_success():
    """AC5: Đóng cảnh báo thành công, cập nhật resolved_at, resolved_by_id và audit log."""
    db = SessionLocalTest()
    now = datetime.now(UTC).replace(tzinfo=None)

    # Tạo cảnh báo mẫu
    alert = Alert(
        charge_point_id=2,
        alert_type="offline",
        status="active",
        severity="critical",
        message="Trụ offline",
        triggered_at=now,
    )
    db.add(alert)
    db.commit()

    resolved = resolve_alert(
        db,
        alert_id=alert.id,
        resolved_by_id=10,
        note="Kỹ thuật đã cắm lại nguồn trụ",
        now=now,
    )
    assert resolved.status == "resolved"
    assert resolved.resolved_by_id == 10
    assert resolved.resolved_at == now
    assert "Kỹ thuật đã cắm lại nguồn trụ" in resolved.message

    # Kiểm tra AuditLog
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.action == "alert.resolve", AuditLog.object_id == str(alert.id))
        .first()
    )
    assert audit is not None
    assert audit.actor_id == 10
    db.close()


def test_new_alert_allowed_after_resolved():
    """Sau khi cảnh báo cũ đã đóng (resolved), nếu sự cố vẫn tiếp diễn thì cho phép sinh cảnh báo mới."""
    db = SessionLocalTest()
    now = datetime.now(UTC).replace(tzinfo=None)

    # Lần 1: quét sinh cảnh báo
    alerts1 = scan_offline_charge_points(db, now=now)
    assert len(alerts1) == 1
    db.commit()

    # Đóng cảnh báo
    resolve_alert(db, alert_id=alerts1[0].id, resolved_by_id=1, now=now)

    # Lần 2: quét lại khi trụ vẫn offline -> sinh cảnh báo mới
    alerts2 = scan_offline_charge_points(db, now=now + timedelta(minutes=10))
    assert len(alerts2) == 1
    assert alerts2[0].id != alerts1[0].id
    assert alerts2[0].status == "active"
    db.close()


def test_auto_resolve_recovered_offline_alerts():
    """Khi trụ trực tuyến trở lại, cảnh báo offline tự động chuyển sang resolved."""
    db = SessionLocalTest()
    now = datetime.now(UTC).replace(tzinfo=None)

    # Tạo cảnh báo offline cho trụ CP 2
    alert = Alert(
        charge_point_id=2,
        alert_type="offline",
        status="active",
        severity="critical",
        message="Trụ offline",
        triggered_at=now,
    )
    db.add(alert)
    db.commit()

    # Giả sử trụ 2 đã online trở lại
    cp2 = db.query(ChargePoint).filter(ChargePoint.id == 2).first()
    cp2.status = "online"
    db.commit()

    resolved_list = auto_resolve_recovered_offline_alerts(db, now=now)
    assert len(resolved_list) == 1
    assert resolved_list[0].id == alert.id
    assert resolved_list[0].status == "resolved"
    assert "Tự động đóng: Trụ đã trực tuyến trở lại" in resolved_list[0].message
    db.close()


def test_scan_alerts_once_job():
    """Kiểm tra hàm scan_alerts_once tích hợp trong jobs.py."""
    db = SessionLocalTest()
    # Chạy scan_alerts_once
    new_count = scan_alerts_once(db)
    assert new_count == 1  # Chỉ có CP 2 bị offline
    db.close()


def test_get_alerts_pagination():
    """Kiểm tra phân trang và bộ lọc trong get_alerts."""
    db = SessionLocalTest()
    now = datetime.now(UTC).replace(tzinfo=None)
    for i in range(15):
        a = Alert(
            charge_point_id=1,
            alert_type="offline",
            status="active" if i % 2 == 0 else "resolved",
            severity="warning",
            message=f"Alert {i}",
            triggered_at=now - timedelta(minutes=i),
        )
        db.add(a)
    db.commit()

    # Lọc active
    active_items, total_active = get_alerts(db, status="active", skip=0, limit=5)
    assert total_active == 8
    assert len(active_items) == 5

    # Phân trang skip
    page2_items, _ = get_alerts(db, status="active", skip=5, limit=5)
    assert len(page2_items) == 3
    db.close()


# ==============================================================================
# 2. TEST ALERTS ROUTER (REST API & PHÂN QUYỀN)
# ==============================================================================


def test_router_list_alerts_operator():
    """Vận hành viên (operator) có quyền xem danh sách cảnh báo."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(2, ["operator"])

    response = client.get("/api/alerts")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert "active_count" in data


def test_router_get_alerts_summary():
    """Lấy thống kê tóm tắt cảnh báo thành công."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])

    response = client.get("/api/alerts/summary")
    assert response.status_code == 200
    data = response.json()
    assert "active_total" in data
    assert "active_offline" in data
    assert "active_connector_error" in data


def test_router_trigger_scan():
    """Admin có thể trigger quét cảnh báo theo yêu cầu."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])

    response = client.post("/api/alerts/scan")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) == 1  # Phát hiện trụ CP_OFFLINE
    assert items[0]["charge_point_code"] == "CP_OFFLINE"


def test_router_resolve_alert():
    """Vận hành viên đóng cảnh báo qua API thành công."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(3, ["operator"])

    # Tạo cảnh báo
    db = SessionLocalTest()
    alert = Alert(
        charge_point_id=2,
        alert_type="offline",
        status="active",
        severity="critical",
        message="Trụ offline",
        triggered_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(alert)
    db.commit()
    alert_id = alert.id
    db.close()

    response = client.post(
        f"/api/alerts/{alert_id}/resolve",
        json={"note": "Đã reset CB điện tại trạm"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "resolved"
    assert data["resolved_by_id"] == 3
    assert "Đã reset CB điện" in data["message"]


def test_router_resolve_not_found():
    """Đóng cảnh báo không tồn tại trả về 404."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])

    response = client.post("/api/alerts/999999/resolve", json={})
    assert response.status_code == 404


def test_router_deny_driver_role():
    """Tài xế (driver) bị từ chối truy cập (HTTP 403 Forbidden)."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(99, ["driver"])

    response = client.get("/api/alerts")
    assert response.status_code == 403

    response = client.post("/api/alerts/scan")
    assert response.status_code == 403
