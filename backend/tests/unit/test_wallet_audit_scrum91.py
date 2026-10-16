"""
Unit tests cho SCRUM-91 / S-56:
Nhật ký thao tác trên giao dịch ví truy được ai làm gì.
Bao phủ:
- Nhật ký nạp tay (manual_topup) ghi đầy đủ người thực hiện, tài xế, số tiền, lý do.
- Điều chỉnh ví (wallet.adjust) cộng/trừ số dư, ghi sổ cái và audit_logs.
- Khóa và mở khóa ví (wallet.lock / wallet.unlock) ghi audit_logs.
- API GET /api/audit lọc theo driver_id, driver (email/tên), action.
- Quyền bảo mật deny-by-default và tính bất biến 405 của audit_logs.
"""


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.user import Role, User, user_roles
from app.services.wallet import (
    adjust_wallet_balance,
    manual_topup,
    set_driver_wallet_lock,
    wallet_totals,
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
    def __init__(self, user_id: int, roles: list[str], email: str = "admin@test.com", full_name: str = "Admin Test"):
        self.id = user_id
        self.email = email
        self.full_name = full_name
        self.roles = [MockRole(r) for r in roles]


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine_test)

    db = SessionLocalTest()
    # Tạo các roles
    role_admin = Role(id=1, name="admin")
    role_operator = Role(id=2, name="operator")
    role_driver = Role(id=3, name="driver")
    db.add_all([role_admin, role_operator, role_driver])
    db.flush()

    # 1. Quản trị viên
    admin = User(
        id=1,
        email="admin@charge.vn",
        password_hash="argon2_hash",
        full_name="Nguyễn Quản Trị",
        is_active=True,
    )
    # 2. Tài xế 1
    driver1 = User(
        id=10,
        email="driver1@gmail.com",
        password_hash="argon2_hash",
        full_name="Tài Xế Một",
        is_active=True,
    )
    # 3. Tài xế 2
    driver2 = User(
        id=20,
        email="driver2@gmail.com",
        password_hash="argon2_hash",
        full_name="Tài Xế Hai",
        is_active=True,
    )
    db.add_all([admin, driver1, driver2])
    db.flush()

    # Gán vai trò
    db.execute(user_roles.insert().values(user_id=1, role_id=1))
    db.execute(user_roles.insert().values(user_id=10, role_id=3))
    db.execute(user_roles.insert().values(user_id=20, role_id=3))

    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=engine_test)
    app.dependency_overrides = previous_overrides


# ==============================================================================
# 1. TEST GHI NHẬT KÝ THAO TÁC VÍ (AC1, AC2, AC3)
# ==============================================================================


def test_manual_topup_writes_audit_log_with_full_details():
    """AC1: Nạp tay ghi rõ người thực hiện, tài xế, số tiền, mã phiếu, lý do."""
    db = SessionLocalTest()

    entry = manual_topup(
        db=db,
        admin_user_id=1,
        driver_user_id=10,
        amount_vnd=100000,
        receipt_code="PT-20261013-001",
        note="Thu tiền mặt tại văn phòng",
    )
    db.commit()

    assert entry.id is not None
    assert entry.amount_vnd == 100000

    # Kiểm tra dòng audit_logs
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.action == "wallet.manual_topup", AuditLog.target_user_id == 10)
        .first()
    )
    assert audit is not None
    assert audit.actor_id == 1
    assert audit.actor_email == "admin@charge.vn"
    assert audit.actor_name == "Nguyễn Quản Trị"
    assert audit.target_user_id == 10
    assert audit.details["amount_vnd"] == 100000
    assert audit.details["receipt_code"] == "PT-20261013-001"
    assert audit.details["reason"] == "Thu tiền mặt tại văn phòng"
    assert audit.details["driver_email"] == "driver1@gmail.com"
    db.close()


def test_adjust_wallet_balance_positive_and_negative():
    """AC2: Điều chỉnh ví (cộng/trừ) ghi nhận sổ cái và nhật ký wallet.adjust."""
    db = SessionLocalTest()
    admin = db.query(User).filter(User.id == 1).first()

    # 1. Điều chỉnh cộng tiền bồi hoàn (+50,000 VND)
    entry_credit = adjust_wallet_balance(
        db=db,
        admin_user=admin,
        driver_user_id=10,
        amount_vnd=50000,
        reason="Bồi hoàn phiên sạc bị gián đoạn",
        reference_code="REF-001",
    )
    db.commit()

    assert entry_credit.amount_vnd == 50000
    assert entry_credit.entry_type == "adjustment"
    assert wallet_totals(db, 10)["balance_vnd"] == 50000

    audit_credit = (
        db.query(AuditLog)
        .filter(AuditLog.action == "wallet.adjust", AuditLog.object_id == str(entry_credit.id))
        .first()
    )
    assert audit_credit is not None
    assert audit_credit.target_user_id == 10
    assert audit_credit.actor_email == "admin@charge.vn"
    assert audit_credit.details["amount_vnd"] == 50000
    assert audit_credit.details["reason"] == "Bồi hoàn phiên sạc bị gián đoạn"

    # 2. Điều chỉnh trừ tiền (-20,000 VND)
    entry_debit = adjust_wallet_balance(
        db=db,
        admin_user=admin,
        driver_user_id=10,
        amount_vnd=-20000,
        reason="Khấu trừ bù cước lỗi kết nối",
        reference_code="REF-002",
    )
    db.commit()

    assert entry_debit.amount_vnd == -20000
    assert wallet_totals(db, 10)["balance_vnd"] == 30000

    audit_debit = (
        db.query(AuditLog)
        .filter(AuditLog.action == "wallet.adjust", AuditLog.object_id == str(entry_debit.id))
        .first()
    )
    assert audit_debit is not None
    assert audit_debit.details["amount_vnd"] == -20000
    db.close()


def test_adjust_wallet_validation_errors():
    """AC2 validation: Số tiền bằng 0 hoặc lý do thiếu bị từ chối."""
    db = SessionLocalTest()
    admin = db.query(User).filter(User.id == 1).first()

    # Tiền bằng 0
    with pytest.raises(ValueError, match="Số tiền điều chỉnh phải khác 0"):
        adjust_wallet_balance(
            db=db, admin_user=admin, driver_user_id=10, amount_vnd=0, reason="Hợp lệ"
        )

    # Lý do ngắn hơn 3 ký tự
    with pytest.raises(ValueError, match="Lý do điều chỉnh ví bắt buộc có tối thiểu 3 ký tự"):
        adjust_wallet_balance(
            db=db, admin_user=admin, driver_user_id=10, amount_vnd=10000, reason="ok"
        )
    db.close()


def test_lock_and_unlock_driver_wallet_writes_audit():
    """AC3: Khóa và mở khóa ví ghi nhận audit_logs (wallet.lock / wallet.unlock)."""
    db = SessionLocalTest()
    admin = db.query(User).filter(User.id == 1).first()

    # Khóa ví
    driver_locked = set_driver_wallet_lock(
        db=db,
        admin_user=admin,
        driver_user_id=10,
        locked=True,
        reason="Nghi vấn giao dịch bất thường",
    )
    db.commit()
    assert driver_locked.is_active is False

    audit_lock = (
        db.query(AuditLog)
        .filter(AuditLog.action == "wallet.lock", AuditLog.target_user_id == 10)
        .first()
    )
    assert audit_lock is not None
    assert audit_lock.details["reason"] == "Nghi vấn giao dịch bất thường"
    assert audit_lock.details["is_locked"] is True

    # Mở khóa ví
    driver_unlocked = set_driver_wallet_lock(
        db=db,
        admin_user=admin,
        driver_user_id=10,
        locked=False,
        reason="Đã xác minh thông tin tài xế an toàn",
    )
    db.commit()
    assert driver_unlocked.is_active is True

    audit_unlock = (
        db.query(AuditLog)
        .filter(AuditLog.action == "wallet.unlock", AuditLog.target_user_id == 10)
        .first()
    )
    assert audit_unlock is not None
    assert audit_unlock.details["reason"] == "Đã xác minh thông tin tài xế an toàn"
    assert audit_unlock.details["is_locked"] is False
    db.close()


# ==============================================================================
# 2. TEST REST API VÍ ADMIN & AUDIT TRA CỨU (AC4, AC5)
# ==============================================================================


def test_api_admin_adjust_wallet_endpoint():
    """Admin gọi endpoint POST /api/wallet/admin/wallets/{id}/adjust thành công."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(
        1, ["admin"], email="admin@charge.vn", full_name="Admin Test"
    )

    response = client.post(
        "/api/wallet/admin/wallets/10/adjust",
        json={
            "amount_vnd": 35000,
            "reason": "Hoàn tiền phiên 99",
            "reference_code": "REF-API-01",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["amount_vnd"] == 35000
    assert data["driver_id"] == 10
    assert data["balance_after_vnd"] == 35000


def test_api_admin_lock_and_unlock_wallet_endpoints():
    """Admin gọi endpoint lock/unlock ví thành công."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(
        1, ["admin"], email="admin@charge.vn"
    )

    # Lock
    resp_lock = client.post(
        "/api/wallet/admin/wallets/10/lock",
        json={"reason": "Tạm khóa do khiếu nại nợ cước"},
    )
    assert resp_lock.status_code == 200
    assert resp_lock.json()["status"] == "locked"

    # Unlock
    resp_unlock = client.post(
        "/api/wallet/admin/wallets/10/unlock",
        json={"reason": "Mở khóa sau khi nạp bù cước"},
    )
    assert resp_unlock.status_code == 200
    assert resp_unlock.json()["status"] == "active"


def test_filter_audit_logs_by_driver_id():
    """AC4: Trang nhật ký kiểm toán lọc được theo driver_id."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])

    # Tạo audit log cho Driver 10 và Driver 20
    db = SessionLocalTest()
    admin = db.query(User).filter(User.id == 1).first()
    adjust_wallet_balance(
        db=db, admin_user=admin, driver_user_id=10, amount_vnd=15000, reason="Cộng tiền D1"
    )
    adjust_wallet_balance(
        db=db, admin_user=admin, driver_user_id=20, amount_vnd=25000, reason="Cộng tiền D2"
    )
    db.commit()
    db.close()

    # Lọc theo driver_id = 10
    response = client.get("/api/audit?driver_id=10")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert item["target_user_id"] == 10


def test_filter_audit_logs_by_driver_query():
    """AC4: Lọc theo chuỗi tìm kiếm tài xế (email hoặc tên)."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["operator"])

    db = SessionLocalTest()
    admin = db.query(User).filter(User.id == 1).first()
    adjust_wallet_balance(
        db=db, admin_user=admin, driver_user_id=10, amount_vnd=15000, reason="Cộng tiền D1"
    )
    db.commit()
    db.close()

    # Lọc theo email tài xế
    response = client.get("/api/audit?driver=driver1@gmail.com")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    assert items[0]["target_user_id"] == 10

    # Lọc tên không tồn tại -> trả về rỗng
    resp_none = client.get("/api/audit?driver=khong_ton_tai")
    assert resp_none.status_code == 200
    assert len(resp_none.json()["items"]) == 0


def test_filter_audit_logs_by_action():
    """Lọc theo action cụ thể (wallet.adjust)."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])

    db = SessionLocalTest()
    admin = db.query(User).filter(User.id == 1).first()
    adjust_wallet_balance(
        db=db, admin_user=admin, driver_user_id=10, amount_vnd=15000, reason="Điều chỉnh"
    )
    set_driver_wallet_lock(
        db=db, admin_user=admin, driver_user_id=10, locked=True, reason="Khóa ví"
    )
    db.commit()
    db.close()

    response = client.get("/api/audit?action=wallet.adjust")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert item["action"] == "wallet.adjust"


def test_audit_logs_immutable_rejects_mutation():
    """AC5: PUT/PATCH/DELETE nhật ký kiểm toán bị từ chối bằng 405 Method Not Allowed."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(1, ["admin"])

    assert client.put("/api/audit/1", json={}).status_code == 405
    assert client.patch("/api/audit/1", json={}).status_code == 405
    assert client.delete("/api/audit/1").status_code == 405


def test_deny_driver_from_admin_wallet_endpoints():
    """Tài xế bị từ chối khi gọi API điều chỉnh/khóa ví (403 Forbidden)."""
    app.dependency_overrides[get_current_user] = lambda: MockUser(10, ["driver"])

    assert client.post("/api/wallet/admin/wallets/10/adjust", json={"amount_vnd": 1000, "reason": "hack"}).status_code == 403
    assert client.post("/api/wallet/admin/wallets/10/lock", json={"reason": "hack"}).status_code == 403
    assert client.get("/api/audit").status_code == 403
