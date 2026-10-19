"""SCRUM-86 / SCRUM-254: Partner revenue sharing UI permissions and page structure."""

import csv
from io import StringIO
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.revenue_share_contract import RevenueShareContract
from app.models.station import Station
from app.models.user import Role, User


def test_revenue_sharing_page_permissions(db_session):
    accountant = User(id=8601, email="acc@example.test", password_hash="h", full_name="Accountant", is_active=True)
    admin = User(id=8602, email="admin@example.test", password_hash="h", full_name="Admin", is_active=True)
    driver = User(id=8603, email="driver@example.test", password_hash="h", full_name="Driver", is_active=True)
    station_owner = User(id=8604, email="owner@example.test", password_hash="h", full_name="Owner", is_active=True)

    role_acc = Role(id=8601, name="accountant")
    role_admin = Role(id=8602, name="admin")
    role_driver = Role(id=8603, name="driver")
    role_owner = Role(id=8604, name="station_owner")

    accountant.roles = [role_acc]
    admin.roles = [role_admin]
    driver.roles = [role_driver]
    station_owner.roles = [role_owner]

    db_session.add_all([accountant, admin, driver, station_owner, role_acc, role_admin, role_driver, role_owner])
    db_session.commit()

    client = TestClient(app)

    # Driver is forbidden
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=driver.id, roles=driver.roles, full_name=driver.full_name
    )
    assert client.get("/sessions/revenue-sharing").status_code == 403

    # Station owner is forbidden
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=station_owner.id, roles=station_owner.roles, full_name=station_owner.full_name
    )
    assert client.get("/sessions/revenue-sharing").status_code == 403

    # Accountant can view
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=accountant.id, roles=accountant.roles, full_name=accountant.full_name
    )
    res_acc = client.get("/sessions/revenue-sharing")
    assert res_acc.status_code == 200
    assert "Chia doanh thu cho đối tác" in res_acc.text
    assert "Đối tác" in res_acc.text
    assert "Chính sách" in res_acc.text
    assert "Tỉ lệ áp dụng" in res_acc.text
    assert "Doanh thu làm cơ sở" in res_acc.text
    assert "Số tiền được chia" in res_acc.text
    assert "Doanh thu làm cơ sở phân chia" in res_acc.text
    assert "Tỉ lệ của đối tác và nền tảng được lấy từ hợp đồng" in res_acc.text
    assert "Xem chính sách, tỉ lệ áp dụng và số tiền được chia cho từng đối tác" in res_acc.text
    assert "Tổng số tiền được chia theo bảng kê" in res_acc.text
    assert "60%" not in res_acc.text
    assert "Báo cáo chưa sẵn sàng. Vui lòng thử lại sau." not in res_acc.text
    assert 'id="rev-share-partner" class="form-select"' in res_acc.text

    # Verify no backend internal names or removed indicators leaked into HTML
    assert "Tạ Như Vinh" not in res_acc.text
    assert "SCRUM-86" not in res_acc.text
    assert "SCRUM-254" not in res_acc.text
    assert "Tỉ lệ áp dụng bình quân" not in res_acc.text
    assert "Số hợp đồng đối tác" not in res_acc.text

    # Admin can view
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=admin.id, roles=admin.roles, full_name=admin.full_name
    )
    res_admin = client.get("/sessions/revenue-sharing")
    assert res_admin.status_code == 200

    app.dependency_overrides.clear()


def test_revenue_share_contract_api_versions_percentages_and_historical_dates(db_session):
    owner = User(
        id=8610, email="contract-owner@example.test", password_hash="h",
        full_name="Partner", is_active=True,
    )
    accountant = User(
        id=8611, email="contract-accountant@example.test", password_hash="h",
        full_name="Accountant", is_active=True,
    )
    db_session.add_all([owner, accountant])
    db_session.flush()
    db_session.add(Station(id=8610, name="Contract station", owner_id=owner.id, status="active"))
    db_session.commit()

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=accountant.id,
        email=accountant.email,
        full_name=accountant.full_name,
        roles=[SimpleNamespace(name="accountant")],
    )
    client = TestClient(app)
    try:
        response = client.post(
            "/api/subscriptions/revenue-share/contracts",
            json={
                "station_owner_id": owner.id,
                "partner_share_percent": 60,
                "platform_share_percent": 40,
                "effective_from": "2026-11-01T00:00:00Z",
            },
        )
        assert response.status_code == 201
        first = response.json()

        next_response = client.post(
            "/api/subscriptions/revenue-share/contracts",
            json={
                "station_owner_id": owner.id,
                "partner_share_percent": 37.5,
                "platform_share_percent": 62.5,
                "effective_from": "2026-12-01T00:00:00Z",
            },
        )
        assert next_response.status_code == 201
        next_contract = next_response.json()
        first_model = db_session.get(RevenueShareContract, first["id"])
        assert first_model.effective_to.isoformat() == "2026-12-01T00:00:00"

        contracts = client.get("/api/subscriptions/revenue-share/contracts")
        assert contracts.status_code == 200
        assert [item["id"] for item in contracts.json()["items"]] == [next_contract["id"], first["id"]]

        invalid_split = client.post(
            "/api/subscriptions/revenue-share/contracts",
            json={
                "station_owner_id": owner.id,
                "partner_share_percent": 60,
                "platform_share_percent": 39,
                "effective_from": "2027-01-01T00:00:00Z",
            },
        )
        assert invalid_split.status_code == 422

        query = {"date_from": "2026-11-01", "date_to": "2026-11-30"}
        report = client.get("/api/subscriptions/revenue-share", params=query)
        exported = client.get("/api/subscriptions/revenue-share.csv", params=query)
        assert report.status_code == exported.status_code == 200
        assert exported.content.startswith(b"\xef\xbb\xbf")
        rows = list(csv.DictReader(StringIO(exported.content.decode("utf-8-sig"))))
        assert rows[0]["row_type"] == "TOTAL"
        assert int(rows[0]["base_revenue_vnd"]) == report.json()["totals"]["base_revenue_vnd"]
        assert int(rows[0]["shared_amount_vnd"]) == report.json()["totals"]["shared_amount_vnd"]
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
