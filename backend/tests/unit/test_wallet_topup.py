"""Unit tests for SCRUM-69: Sandbox wallet top-up and ledger consistency."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.payment_transaction import PaymentTransaction
from app.models.user import Role, User
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.wallet import (
    create_sandbox_topup_request,
    deduct_session_charge,
    has_minimum_balance,
    process_sandbox_webhook,
    refund_wallet_charge,
    wallet_totals,
)

engine_test = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


class MockRole:
    def __init__(self, name: str) -> None:
        self.name = name


class MockUser:
    def __init__(
        self, user_id: int, roles: list[str], email: str = "driver@demo.vn"
    ) -> None:
        self.id = user_id
        self.roles = [MockRole(r) for r in roles]
        self.email = email
        self.full_name = f"User {user_id}"


@pytest.fixture(autouse=True)
def setup_database() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=engine_test)
    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    driver_user = User(
        id=10,
        email="driver@demo.vn",
        password_hash="hashed",
        full_name="Driver One",
        is_active=True,
    )
    other_user = User(
        id=20,
        email="other@demo.vn",
        password_hash="hashed",
        full_name="Driver Two",
        is_active=True,
    )
    role_driver = Role(id=1, name="driver")
    db.add_all([driver_user, other_user, role_driver])
    db.commit()
    db.close()

    yield

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine_test)


def test_create_sandbox_topup_success() -> None:
    """SCRUM-196 / SCRUM-197: Driver tạo yêu cầu nạp tiền sandbox thành công."""
    mock_driver = MockUser(user_id=10, roles=["driver"])
    app.dependency_overrides[get_current_user] = lambda: mock_driver

    response = client.post(
        "/api/wallet/topups/sandbox",
        json={"amount_vnd": 100_000},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["amount_vnd"] == 100_000
    assert data["status"] == "pending"
    assert data["provider"] == "sandbox"
    assert data["order_code"].startswith("TOPUP-")
    assert "sandbox-checkout" in data["payment_url"]


def test_create_sandbox_topup_amount_limits() -> None:
    """Kiểm tra giới hạn số tiền nạp: tối thiểu 10k, tối đa 10M."""
    mock_driver = MockUser(user_id=10, roles=["driver"])
    app.dependency_overrides[get_current_user] = lambda: mock_driver

    # Dưới 10.000 VNĐ -> 422
    resp_low = client.post(
        "/api/wallet/topups/sandbox", json={"amount_vnd": 5_000}
    )
    assert resp_low.status_code == 422

    # Trên 10.000.000 VNĐ -> 422
    resp_high = client.post(
        "/api/wallet/topups/sandbox", json={"amount_vnd": 15_000_000}
    )
    assert resp_high.status_code == 422


def test_create_sandbox_topup_forbidden_non_driver() -> None:
    """Tài khoản không có quyền driver bị từ chối 403."""
    mock_operator = MockUser(user_id=99, roles=["operator"])
    app.dependency_overrides[get_current_user] = lambda: mock_operator

    response = client.post(
        "/api/wallet/topups/sandbox",
        json={"amount_vnd": 50_000},
    )
    assert response.status_code == 403


def test_sandbox_webhook_success_credits_wallet() -> None:
    """SCRUM-198: Webhook thành công cộng tiền vào ví và tạo ledger entry."""
    db = TestingSessionLocal()
    tx = create_sandbox_topup_request(db, user_id=10, amount_vnd=200_000)
    db.commit()
    order_code = tx.order_code
    db.close()

    # Cổng sandbox gọi webhook thông báo thanh toán thành công
    resp = client.post(
        "/api/wallet/topups/sandbox/webhook",
        json={"order_code": order_code, "status": "success"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["balance_vnd"] == 200_000

    # Kiểm tra số dư trong DB
    db_verify = TestingSessionLocal()
    totals = wallet_totals(db_verify, user_id=10)
    assert totals["balance_vnd"] == 200_000

    entry = (
        db_verify.query(WalletLedgerEntry)
        .filter_by(receipt_code=order_code)
        .first()
    )
    assert entry is not None
    assert entry.entry_type == "sandbox_topup"
    assert entry.amount_vnd == 200_000
    db_verify.close()


def test_sandbox_webhook_idempotent() -> None:
    """SCRUM-198: Webhook gọi lại nhiều lần chỉ ghi nhận 1 lần duy nhất."""
    db = TestingSessionLocal()
    tx = create_sandbox_topup_request(db, user_id=10, amount_vnd=150_000)
    db.commit()
    order_code = tx.order_code
    db.close()

    # Gọi lần 1
    resp1 = client.post(
        "/api/wallet/topups/sandbox/webhook",
        json={"order_code": order_code, "status": "success"},
    )
    assert resp1.status_code == 200
    assert resp1.json()["balance_vnd"] == 150_000

    # Gọi lần 2 (retry)
    resp2 = client.post(
        "/api/wallet/topups/sandbox/webhook",
        json={"order_code": order_code, "status": "success"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["balance_vnd"] == 150_000

    # Số dư vẫn chỉ là 150.000, không bị nhân đôi
    db_verify = TestingSessionLocal()
    totals = wallet_totals(db_verify, user_id=10)
    assert totals["balance_vnd"] == 150_000
    count = (
        db_verify.query(WalletLedgerEntry)
        .filter_by(receipt_code=order_code)
        .count()
    )
    assert count == 1
    db_verify.close()


def test_sandbox_webhook_failed_does_not_credit() -> None:
    """SCRUM-201: Webhook thất bại không cộng tiền ví."""
    db = TestingSessionLocal()
    tx = create_sandbox_topup_request(db, user_id=10, amount_vnd=300_000)
    db.commit()
    order_code = tx.order_code
    db.close()

    resp = client.post(
        "/api/wallet/topups/sandbox/webhook",
        json={
            "order_code": order_code,
            "status": "failed",
            "failure_reason": "Thẻ hết hạn hoặc không đủ số dư",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"
    assert resp.json()["balance_vnd"] == 0

    db_verify = TestingSessionLocal()
    tx_updated = (
        db_verify.query(PaymentTransaction)
        .filter_by(order_code=order_code)
        .first()
    )
    assert tx_updated.status == "failed"
    assert tx_updated.failure_reason == "Thẻ hết hạn hoặc không đủ số dư"
    totals = wallet_totals(db_verify, user_id=10)
    assert totals["balance_vnd"] == 0
    db_verify.close()


def test_simulate_pay_driver() -> None:
    """Tài xế giả lập thanh toán nhanh trên giao diện."""
    mock_driver = MockUser(user_id=10, roles=["driver"])
    app.dependency_overrides[get_current_user] = lambda: mock_driver

    db = TestingSessionLocal()
    tx = create_sandbox_topup_request(db, user_id=10, amount_vnd=50_000)
    db.commit()
    order_code = tx.order_code
    db.close()

    resp = client.post(
        "/api/wallet/topups/sandbox/simulate-pay",
        json={"order_code": order_code, "status": "success"},
    )
    assert resp.status_code == 200
    assert resp.json()["balance_vnd"] == 50_000


def test_simulate_pay_forbidden_other_user() -> None:
    """Tài xế không được thanh toán đơn của tài khoản khác."""
    mock_other = MockUser(user_id=20, roles=["driver"])
    app.dependency_overrides[get_current_user] = lambda: mock_other

    db = TestingSessionLocal()
    tx = create_sandbox_topup_request(db, user_id=10, amount_vnd=50_000)
    db.commit()
    order_code = tx.order_code
    db.close()

    resp = client.post(
        "/api/wallet/topups/sandbox/simulate-pay",
        json={"order_code": order_code, "status": "success"},
    )
    assert resp.status_code == 403


def test_list_my_topup_history() -> None:
    """SCRUM-197: Tài xế xem lịch sử các lần nạp tiền của mình."""
    mock_driver = MockUser(user_id=10, roles=["driver"])
    app.dependency_overrides[get_current_user] = lambda: mock_driver

    db = TestingSessionLocal()
    create_sandbox_topup_request(db, user_id=10, amount_vnd=50_000)
    create_sandbox_topup_request(db, user_id=10, amount_vnd=100_000)
    db.commit()
    db.close()

    resp = client.get("/api/wallet/topups")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_check_balance_minimum_threshold() -> None:
    """SCRUM-199 / SCRUM-72: Kiểm tra số dư đạt ngưỡng tối thiểu trước khi sạc."""
    mock_driver = MockUser(user_id=10, roles=["driver"])
    app.dependency_overrides[get_current_user] = lambda: mock_driver

    # Chưa nạp -> số dư 0 < 50k
    resp1 = client.get("/api/wallet/check-balance?min_amount_vnd=50000")
    assert resp1.status_code == 200
    assert resp1.json()["balance_vnd"] == 0
    assert resp1.json()["has_minimum_balance"] is False

    # Nạp 100k -> số dư 100k >= 50k
    db = TestingSessionLocal()
    tx = create_sandbox_topup_request(db, user_id=10, amount_vnd=100_000)
    process_sandbox_webhook(db, tx.order_code, status="success")
    db.commit()
    db.close()

    resp2 = client.get("/api/wallet/check-balance?min_amount_vnd=50000")
    assert resp2.status_code == 200
    assert resp2.json()["balance_vnd"] == 100_000
    assert resp2.json()["has_minimum_balance"] is True


def test_service_deduct_and_refund() -> None:
    """Kiểm tra logic service: trừ tiền phiên sạc và hoàn tiền."""
    db = TestingSessionLocal()
    # Nạp 100k
    tx = create_sandbox_topup_request(db, user_id=10, amount_vnd=100_000)
    process_sandbox_webhook(db, tx.order_code, status="success")
    db.commit()

    assert has_minimum_balance(db, user_id=10, min_amount_vnd=50_000) is True

    # Trừ 30k phiên sạc #101
    entry_charge = deduct_session_charge(
        db, user_id=10, session_id=101, amount_vnd=30_000
    )
    db.commit()
    assert entry_charge.amount_vnd == -30_000
    assert wallet_totals(db, user_id=10)["balance_vnd"] == 70_000

    # Trừ lại cùng session_id #101 (idempotent)
    entry_repeat = deduct_session_charge(
        db, user_id=10, session_id=101, amount_vnd=30_000
    )
    assert entry_repeat.id == entry_charge.id
    assert wallet_totals(db, user_id=10)["balance_vnd"] == 70_000

    # Hoàn tiền 30k
    entry_refund = refund_wallet_charge(
        db,
        user_id=10,
        original_receipt_code="CHARGE-101",
        amount_vnd=30_000,
        reason="Phiên sạc lỗi kỹ thuật",
    )
    db.commit()
    assert entry_refund.amount_vnd == 30_000
    assert wallet_totals(db, user_id=10)["balance_vnd"] == 100_000
    db.close()
