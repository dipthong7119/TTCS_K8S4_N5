"""SCRUM-86 / SCRUM-254: Partner revenue sharing UI permissions and page structure."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.main import app
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
    assert "Chủ trạm nhận 60% phí gói thuê bao" in res_acc.text
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
