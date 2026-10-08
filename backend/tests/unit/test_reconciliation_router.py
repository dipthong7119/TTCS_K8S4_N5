"""
test_reconciliation_router.py — Unit tests cho API GET /api/reconciliation/kwh (SCRUM-183 / SCRUM-184).

Phụ trách: Hoàng Văn Đức
Kiểm tra:
- Phân quyền (admin, operator được phép; driver bị 403; chưa đăng nhập bị 401/403).
- Định dạng trả về đáp ứng yêu cầu của frontend (metadata, summary, sessions).
- Fallback dữ liệu mẫu khi chưa có file kết quả từ SCRUM-182.
- Đối chiếu thành công khi có kết quả thật từ SCRUM-182.
"""

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.charge_point import ChargePoint
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.models.user import User
from app.routers import reconciliation

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


client = TestClient(app)


class MockRole:
    def __init__(self, name: str):
        self.name = name


class MockUser:
    def __init__(self, user_id: int, roles: list[str]):
        self.id = user_id
        self.email = "test@example.com"
        self.full_name = "User Test"
        self.roles = [MockRole(r) for r in roles]


@pytest.fixture(autouse=True)
def setup_db():
    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine_test)

    db = SessionLocalTest()
    user = User(id=1, email="admin@test.com", password_hash="123", full_name="Admin Test")
    station = Station(id=1, name="Trạm Hà Nội", owner_id=1, status="active")
    cp = ChargePoint(id=1, code="CP01", station_id=1, status="online")
    db.add_all([user, station, cp])
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine_test)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def test_reconciliation_requires_authentication():
    """Chưa đăng nhập -> bị chặn bởi role guard (401 hoặc 403)."""
    resp = client.get("/api/reconciliation/kwh")
    assert resp.status_code in (401, 403)


def test_reconciliation_driver_forbidden():
    """Role 'driver' không có quyền xem bảng đối chiếu kWh -> 403."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(2, ["driver"])
    resp = client.get("/api/reconciliation/kwh")
    assert resp.status_code == 403


def test_reconciliation_admin_access_sample_data():
    """Role 'admin' được phép truy cập, trả về đúng cấu trúc metadata, summary, sessions."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])
    resp = client.get("/api/reconciliation/kwh")
    assert resp.status_code == 200

    data = resp.json()
    assert "metadata" in data
    assert "summary" in data
    assert "sessions" in data

    meta = data["metadata"]
    assert "tolerance_kwh" in meta
    assert "is_sample" in meta

    summary = data["summary"]
    assert "total_sessions" in summary
    assert "matched_sessions" in summary
    assert "mismatched_sessions" in summary
    assert "match_percentage" in summary
    assert "verdict" in summary
    assert summary["verdict"] in ("PASSED", "FAILED")


def test_reconciliation_operator_access():
    """Role 'operator' cũng có quyền truy cập."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(3, ["operator"])
    resp = client.get("/api/reconciliation/kwh")
    assert resp.status_code == 200


def test_reconciliation_with_scrum182_file(tmp_path, monkeypatch):
    """Khi có file kết quả SCRUM-182 từ kịch bản của Tú, API đối chiếu thật và trả về is_sample=False."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])

    # Tạo session trong DB để đối chiếu
    db = SessionLocalTest()
    s = ChargingSession(
        id=2001,
        charge_point_id=1,
        charge_point_code="CP01",
        station_id=1,
        station_name="Trạm Hà Nội",
        connector_number=1,
        meter_start_wh=10000,
        meter_stop_wh=20000,
        energy_kwh=10.0,
        started_at=datetime.now(UTC).replace(tzinfo=None),
        ended_at=datetime.now(UTC).replace(tzinfo=None),
        status="completed",
    )
    db.add(s)
    db.commit()
    db.close()

    fake_scrum182_data = {
        "scrum_task": "SCRUM-182",
        "generated_at": datetime.now(UTC).isoformat(),
        "charger_count": 1,
        "items": [
            {
                "code": "CP01",
                "transaction_id": 2001,
                "do_disconnect": True,
                "disconnect_count": 1,
                "meter_start_wh": 10000,
                "meter_stop_wh": 20000,
                "expected_kwh": 10.0,
                "db_kwh": 10.0,
                "db_status": "completed",
                "errors": [],
            }
        ],
    }

    ketqua_dir = tmp_path / "ketqua"
    ketqua_dir.mkdir(parents=True)
    scrum182_path = ketqua_dir / "scrum182_kwh_result.json"
    scrum182_path.write_text(json.dumps(fake_scrum182_data, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(reconciliation, "_get_project_paths", lambda: (ketqua_dir, tmp_path / "static"))

    resp = client.get("/api/reconciliation/kwh")
    assert resp.status_code == 200
    data = resp.json()

    assert data["metadata"]["is_sample"] is False
    assert data["summary"]["total_sessions"] == 1
    assert data["summary"]["matched_sessions"] == 1
    assert data["summary"]["verdict"] == "PASSED"
    assert len(data["sessions"]) == 1
    session_item = data["sessions"][0]
    assert session_item["session_id"] == 2001
    assert session_item["charge_point_code"] == "CP01"
    assert session_item["system_kwh"] == 10.0
    assert session_item["simulator_kwh"] == 10.0
    assert session_item["difference_kwh"] == 0.0
    assert session_item["status"] == "MATCH"
