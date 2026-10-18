"""
Unit tests cho SCRUM-92 / S-57:
Tài xế yêu cầu xoá dữ liệu cá nhân và lịch sử di chuyển theo Nghị định 13/2023/NĐ-CP.
Bao phủ:
- AC1: Tài xế gửi yêu cầu xóa dữ liệu (kiểm tra điều kiện: ví số dư > 0, phiên đang sạc, đặt chỗ, chống trùng).
- AC2: Tài xế xem yêu cầu của mình; Quản trị viên xem danh sách yêu cầu với bộ lọc.
- AC3: Quản trị viên phê duyệt và thực hiện ẩn danh hóa toàn diện không thể đảo ngược (phiên sạc, thẻ RFID, đặt chỗ, tài khoản), bảo toàn doanh thu và sổ cái ví.
- AC4: Quản trị viên từ chối yêu cầu kèm lý do bắt buộc.
- AC5: Phân quyền chặt chẽ (deny-by-default, driver không thể gọi admin endpoint, 401/403).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.charging_invoice import ChargingInvoice
from app.models.charging_session import ChargingSession
from app.models.data_erasure import DataErasureRequest
from app.models.id_tag import IdTag
from app.models.reservation import Reservation, ReservationStatus
from app.models.station import Station
from app.models.station_tariff import StationTariff
from app.models.user import Role, User, user_roles
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.privacy_service import (
    approve_erasure_request,
    create_erasure_request,
    get_my_erasure_requests,
    list_erasure_requests,
    reject_erasure_request,
)

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
    def __init__(
        self,
        user_id: int,
        roles: list[str],
        email: str = "driver@test.local",
        full_name: str = "Driver Test",
    ):
        self.id = user_id
        self.email = email
        self.full_name = full_name
        self.roles = [MockRole(r) for r in roles]


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine_test)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine_test)


def _seed_user_and_roles(db, email: str, full_name: str, role_name: str) -> User:
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        role = Role(name=role_name)
        db.add(role)
        db.flush()

    user = User(
        email=email,
        full_name=full_name,
        password_hash="argon2id$testhash",
        is_active=True,
    )
    db.add(user)
    db.flush()

    db.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user


def test_driver_submit_erasure_request_success():
    """AC1: Tài xế có ví số dư = 0 và không có phiên chạy gửi yêu cầu thành công."""
    db = SessionLocalTest()
    driver = _seed_user_and_roles(db, "driver1@test.local", "Tài Xế Một", "driver")

    req = create_erasure_request(
        db, driver, reason="Tôi muốn xóa dữ liệu theo Nghị định 13"
    )

    assert req.id is not None
    assert req.user_id == driver.id
    assert req.status == "pending"
    assert req.request_reason == "Tôi muốn xóa dữ liệu theo Nghị định 13"

    # Kiểm tra audit log đã được ghi
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "privacy.request_created",
            AuditLog.target_user_id == driver.id,
        )
        .first()
    )
    assert audit is not None
    assert audit.actor_id == driver.id
    db.close()


def test_driver_cannot_submit_when_active_charging_session():
    """AC1: Tài xế đang có phiên sạc hoạt động không thể yêu cầu xóa dữ liệu."""
    db = SessionLocalTest()
    driver = _seed_user_and_roles(db, "driver2@test.local", "Tài Xế Hai", "driver")

    # Tạo phiên sạc active
    session = ChargingSession(
        charge_point_code="CP-01",
        station_name="Trạm Test",
        connector_number=1,
        user_id=driver.id,
        driver_name=driver.full_name,
        meter_start_wh=1000,
        started_at=datetime.now(UTC).replace(tzinfo=None),
        status="active",
    )
    db.add(session)
    db.commit()

    with pytest.raises(Exception) as exc:
        create_erasure_request(db, driver, reason="Xóa dữ liệu")
    assert "phiên sạc đang hoạt động" in str(exc.value.detail)
    db.close()


def test_driver_cannot_submit_when_active_reservation():
    """AC1: Tài xế có đặt chỗ chưa hoàn tất không thể yêu cầu xóa dữ liệu."""
    db = SessionLocalTest()
    driver = _seed_user_and_roles(db, "driver3@test.local", "Tài Xế Ba", "driver")

    reservation = Reservation(
        charge_point_id=1,
        connector_id=1,
        user_id=driver.id,
        id_tag="CARD123",
        start_time=datetime.now(UTC).replace(tzinfo=None),
        expiry_date=datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=30),
        status=ReservationStatus.ACTIVE,
    )
    db.add(reservation)
    db.commit()

    with pytest.raises(Exception) as exc:
        create_erasure_request(db, driver, reason="Xóa dữ liệu")
    assert "đặt chỗ chưa hoàn tất" in str(exc.value.detail)
    db.close()


def test_driver_cannot_submit_when_positive_wallet_balance():
    """AC1: Ví còn số dư dương thì phải xử lý hoàn tiền trước (theo S-57)."""
    db = SessionLocalTest()
    driver = _seed_user_and_roles(db, "driver4@test.local", "Tài Xế Bốn", "driver")

    # Nạp tiền vào ví
    topup = WalletLedgerEntry(
        user_id=driver.id,
        entry_type="manual_topup",
        amount_vnd=100_000,
        idempotency_key="topup-1",
        description="Nạp tiền test",
    )
    db.add(topup)
    db.commit()

    with pytest.raises(Exception) as exc:
        create_erasure_request(db, driver, reason="Xóa dữ liệu")
    assert "Ví tài xế còn số dư" in str(exc.value.detail)
    db.close()


def test_driver_cannot_submit_duplicate_pending_request():
    """AC1: Chống trùng lặp khi đã có yêu cầu pending."""
    db = SessionLocalTest()
    driver = _seed_user_and_roles(db, "driver5@test.local", "Tài Xế Năm", "driver")

    create_erasure_request(db, driver, reason="Yêu cầu lần 1")

    with pytest.raises(Exception) as exc:
        create_erasure_request(db, driver, reason="Yêu cầu lần 2")
    assert "đang chờ xử lý" in str(exc.value.detail)
    assert exc.value.status_code == 409
    db.close()


def test_driver_view_my_requests_and_admin_list_requests():
    """AC2: Tra cứu danh sách yêu cầu của tài xế và của quản trị viên."""
    db = SessionLocalTest()
    driver = _seed_user_and_roles(db, "driver6@test.local", "Tài Xế Sáu", "driver")
    req1 = create_erasure_request(db, driver, reason="Yêu cầu xóa")

    my_reqs = get_my_erasure_requests(db, driver.id)
    assert len(my_reqs) == 1
    assert my_reqs[0].id == req1.id

    admin_items, total = list_erasure_requests(db, status="pending")
    assert total == 1
    assert admin_items[0].id == req1.id
    db.close()


def test_admin_approve_erasure_request_anonymizes_all_driver_data():
    """AC3: Phê duyệt và thực hiện ẩn danh hóa toàn diện không thể đảo ngược."""
    db = SessionLocalTest()
    driver = _seed_user_and_roles(db, "driver7@test.local", "Tài Xế Bảy", "driver")
    admin = _seed_user_and_roles(db, "admin1@test.local", "Quản Trị Viên", "admin")

    # 1. Thẻ RFID
    tag = IdTag(
        id_tag="RFID_DRIVER_7",
        user_id=driver.id,
        is_blocked=False,
    )
    db.add(tag)
    db.flush()

    # 2. Phiên sạc đã kết thúc
    session = ChargingSession(
        charge_point_code="CP-01",
        station_name="Trạm Trung Tâm",
        connector_number=1,
        user_id=driver.id,
        driver_name="Tài Xế Bảy",
        id_tag="RFID_DRIVER_7",
        id_tag_id=tag.id,
        meter_start_wh=1000,
        meter_stop_wh=25000,
        energy_kwh=24.0,
        started_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
        ended_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
        status="completed",
    )
    db.add(session)
    db.flush()

    # 3. Đặt chỗ đã hoàn thành
    reservation = Reservation(
        charge_point_id=1,
        connector_id=1,
        user_id=driver.id,
        id_tag="RFID_DRIVER_7",
        id_tag_id=tag.id,
        start_time=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=3),
        expiry_date=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
        status=ReservationStatus.FULFILLED,
    )
    db.add(reservation)
    db.commit()

    # Tạo yêu cầu
    req = create_erasure_request(db, driver, reason="Quyền được lãng quên theo luật")

    # Quản trị viên duyệt
    approved_req = approve_erasure_request(db, req.id, admin)

    assert approved_req.status == "approved"
    assert approved_req.processed_by == admin.id
    assert approved_req.processed_at is not None

    # Kiểm tra tính toàn vẹn và ẩn danh hóa:
    # 1. Phiên sạc: user_id = None, driver_name = 'ANONYMIZED', id_tag = None
    db.refresh(session)
    assert session.user_id is None
    assert session.driver_name == "ANONYMIZED"
    assert session.id_tag is None
    assert session.id_tag_id is None
    # Số đo và năng lượng bảo toàn 100%
    assert session.energy_kwh == 24.0
    assert session.charge_point_code == "CP-01"

    # 2. Thẻ RFID: bị khóa và mã thẻ được ẩn danh
    db.refresh(tag)
    assert tag.is_blocked is True
    assert tag.id_tag.startswith("ANON_")

    # 3. Đặt chỗ: id_tag = 'ANONYMOUS'
    db.refresh(reservation)
    assert reservation.id_tag == "ANONYMOUS"
    assert reservation.id_tag_id is None

    # 4. Tài khoản người dùng: vô hiệu hóa, ẩn danh email và tên
    db.refresh(driver)
    assert driver.is_active is False
    assert driver.full_name == "Người dùng ẩn danh"
    assert "privacy.local" in driver.email
    assert driver.password_hash == "ANONYMIZED_ACCOUNT_DELETED"

    # 5. Audit log
    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "privacy.request_approved",
            AuditLog.target_user_id == driver.id,
        )
        .first()
    )
    assert audit is not None
    assert audit.actor_id == admin.id
    db.close()


def test_admin_reject_erasure_request_with_reason():
    """AC4: Quản trị viên từ chối yêu cầu và bắt buộc nhập lý do."""
    db = SessionLocalTest()
    driver = _seed_user_and_roles(db, "driver8@test.local", "Tài Xế Tám", "driver")
    admin = _seed_user_and_roles(db, "admin2@test.local", "Quản Trị Viên 2", "admin")

    req = create_erasure_request(db, driver, reason="Yêu cầu xóa")

    # Từ chối không có lý do -> Báo lỗi
    with pytest.raises(Exception):
        reject_erasure_request(db, req.id, admin, rejection_reason="")

    # Từ chối có lý do hợp lệ
    rejected_req = reject_erasure_request(
        db, req.id, admin, rejection_reason="Tài khoản đang có tranh chấp pháp lý."
    )

    assert rejected_req.status == "rejected"
    assert rejected_req.rejection_reason == "Tài khoản đang có tranh chấp pháp lý."
    assert rejected_req.processed_by == admin.id

    audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "privacy.request_rejected",
            AuditLog.target_user_id == driver.id,
        )
        .first()
    )
    assert audit is not None
    assert audit.actor_id == admin.id
    db.close()


def test_api_endpoints_role_guards_and_permissions():
    """AC5: Kiểm tra phân quyền API deny-by-default qua FastAPI router."""
    db = SessionLocalTest()
    driver = _seed_user_and_roles(db, "driver9@test.local", "Tài Xế Chín", "driver")
    admin = _seed_user_and_roles(db, "admin3@test.local", "Quản Trị 3", "admin")
    driver_id = driver.id
    driver_email = driver.email
    driver_name = driver.full_name
    admin_id = admin.id
    admin_email = admin.email
    admin_name = admin.full_name
    db.close()

    # 1. Driver gọi POST /api/privacy/erasure-requests
    app.dependency_overrides[get_current_user] = lambda: MockUser(
        driver_id, ["driver"], driver_email, driver_name
    )
    resp = client.post(
        "/api/privacy/erasure-requests",
        json={"reason": "Xóa thông tin theo NĐ 13"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    req_id = data["id"]

    # 2. Driver xem yêu cầu của mình
    resp = client.get("/api/privacy/erasure-requests/my")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # 3. Driver cố tình gọi endpoint của Admin -> 403 Forbidden
    resp = client.post(f"/api/privacy/admin/erasure-requests/{req_id}/approve")
    assert resp.status_code == 403

    # 4. Admin gọi GET /api/privacy/admin/erasure-requests -> 200 OK
    app.dependency_overrides[get_current_user] = lambda: MockUser(
        admin_id, ["admin"], admin_email, admin_name
    )
    resp = client.get("/api/privacy/admin/erasure-requests")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1

    # 5. Admin phê duyệt yêu cầu -> 200 OK
    resp = client.post(f"/api/privacy/admin/erasure-requests/{req_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_operator_can_view_requests_but_cannot_approve_or_reject():
    """AC5: Operator được xem danh sách yêu cầu nhưng không có quyền duyệt/từ chối."""
    db = SessionLocalTest()
    driver = _seed_user_and_roles(db, "driver10@test.local", "Tài Xế Mười", "driver")
    operator = _seed_user_and_roles(db, "operator1@test.local", "Vận Hành 1", "operator")
    req = create_erasure_request(db, driver, reason="Yêu cầu xóa")
    req_id = req.id
    op_id = operator.id
    op_email = operator.email
    op_name = operator.full_name
    db.close()

    app.dependency_overrides[get_current_user] = lambda: MockUser(
        op_id, ["operator"], op_email, op_name
    )

    # Operator xem danh sách -> 200 OK
    resp = client.get("/api/privacy/admin/erasure-requests")
    assert resp.status_code == 200

    # Operator duyệt -> 403 Forbidden
    resp = client.post(f"/api/privacy/admin/erasure-requests/{req_id}/approve")
    assert resp.status_code == 403

    # Operator từ chối -> 403 Forbidden
    resp = client.post(
        f"/api/privacy/admin/erasure-requests/{req_id}/reject",
        json={"rejection_reason": "Từ chối"},
    )
    assert resp.status_code == 403


def test_approve_or_reject_already_processed_request_fails():
    """Kiểm tra xử lý yêu cầu khi đã được duyệt hoặc từ chối."""
    db = SessionLocalTest()
    driver = _seed_user_and_roles(db, "driver11@test.local", "Tài Xế 11", "driver")
    admin = _seed_user_and_roles(db, "admin4@test.local", "Quản Trị 4", "admin")

    req = create_erasure_request(db, driver, reason="Yêu cầu test")
    approve_erasure_request(db, req.id, admin)

    # Thử duyệt lại yêu cầu đã duyệt -> 400
    with pytest.raises(Exception) as exc:
        approve_erasure_request(db, req.id, admin)
    assert "không thể phê duyệt lại" in str(exc.value.detail)

    # Thử từ chối yêu cầu đã duyệt -> 400
    with pytest.raises(Exception) as exc:
        reject_erasure_request(db, req.id, admin, rejection_reason="Từ chối lại")
    assert "không thể từ chối" in str(exc.value.detail)
    db.close()


def test_erasure_request_not_found():
    """Kiểm tra 404 khi không tìm thấy yêu cầu."""
    db = SessionLocalTest()
    admin = _seed_user_and_roles(db, "admin5@test.local", "Quản Trị 5", "admin")

    with pytest.raises(Exception) as exc:
        approve_erasure_request(db, 999999, admin)
    assert exc.value.status_code == 404

    with pytest.raises(Exception) as exc:
        reject_erasure_request(db, 999999, admin, rejection_reason="Không có")
    assert exc.value.status_code == 404
    db.close()

