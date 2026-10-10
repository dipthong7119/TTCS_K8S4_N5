"""Tests for manual topup."""

import asyncio
import re
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError

from app.core.deps import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.user import Role, User
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.wallet import wallet_balance_matches_ledger

# Use an in-memory SQLite DB for testing
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
    def __init__(self, user_id: int, roles: list[str], email: str = "admin@demo.vn") -> None:
        self.id = user_id
        self.roles = [MockRole(r) for r in roles]
        self.email = email
        self.full_name = f"User {user_id}"

@pytest.fixture(autouse=True)
def setup_database() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=engine_test)
    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    role_driver = Role(id=1, name="driver")
    driver_user = User(
        id=10, email="driver@demo.vn", password_hash="hashed", full_name="Driver", is_active=True
    )
    db.add_all([driver_user, role_driver])
    db.commit()
    
    # Add trigger for test since SQLite memory DB doesn't run alembic migrations by default
    db.execute(text("""
    CREATE TRIGGER IF NOT EXISTS prevent_wallet_ledger_update
    BEFORE UPDATE ON wallet_ledger
    BEGIN
        SELECT RAISE(ABORT, 'wallet_ledger is append-only, UPDATE is not allowed');
    END;
    """))
    db.execute(text("""
    CREATE TRIGGER IF NOT EXISTS prevent_wallet_ledger_delete
    BEFORE DELETE ON wallet_ledger
    BEGIN
        SELECT RAISE(ABORT, 'wallet_ledger is append-only, DELETE is not allowed');
    END;
    """))
    db.commit()
    
    db.close()

    # Default to admin
    app.dependency_overrides[get_current_user] = lambda: MockUser(user_id=1, roles=["admin"])

    yield

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine_test)


def test_ac1_manual_topup_success() -> None:
    """AC1: nạp 500.000 vào ví chưa có, nạp tiếp 200.000"""
    resp1 = client.post(
        "/api/wallet/admin/wallets/10/manual-topups",
        json={"amount": 500000, "receipt_code": "pt-001"}
    )
    assert resp1.status_code == 201
    data1 = resp1.json()
    assert data1["amount"] == 500000
    assert data1["balance_after"] == 500000
    assert data1["receipt_code"] == "PT-001"
    
    # Nạp tiếp 200k
    resp2 = client.post(
        "/api/wallet/admin/wallets/10/manual-topups",
        json={"amount": 200000, "receipt_code": "PT-002"}
    )
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert data2["balance_after"] == 700000

    # Kiểm tra DB
    db = TestingSessionLocal()
    assert wallet_balance_matches_ledger(db, 10) is True
    entries = db.query(WalletLedgerEntry).filter_by(user_id=10).all()
    assert len(entries) == 2
    db.close()


def test_ac2_duplicate_receipt_code() -> None:
    """AC2: nạp lại cùng mã phiếu (cả khi khác tài xế, khác hoa/thường)"""
    client.post(
        "/api/wallet/admin/wallets/10/manual-topups",
        json={"amount": 500000, "receipt_code": "PT-001"}
    )
    # Cùng mã phiếu, khác hoa/thường
    resp = client.post(
        "/api/wallet/admin/wallets/10/manual-topups",
        json={"amount": 100000, "receipt_code": "pt-001"}
    )
    assert resp.status_code == 409
    
    db = TestingSessionLocal()
    assert wallet_balance_matches_ledger(db, 10) is True
    entries = db.query(WalletLedgerEntry).filter_by(user_id=10).all()
    assert len(entries) == 1
    db.close()


@pytest.mark.parametrize("role", ["accountant", "operator", "station_owner", "driver"])
def test_ac3_role_authorization(role: str) -> None:
    """AC3: gọi API bằng từng vai trò bị 403"""
    app.dependency_overrides[get_current_user] = lambda: MockUser(user_id=2, roles=[role])
    resp = client.post(
        "/api/wallet/admin/wallets/10/manual-topups",
        json={"amount": 500000, "receipt_code": f"PT-{role}"}
    )
    assert resp.status_code == 403


def test_ac3_unauthorized() -> None:
    """Chưa đăng nhập"""
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    resp = client.post(
        "/api/wallet/admin/wallets/10/manual-topups",
        json={"amount": 500000, "receipt_code": "PT-UNAUTH"}
    )
    assert resp.status_code == 401


@pytest.mark.parametrize("payload, expected_status", [
    ({"amount": 0, "receipt_code": "PT-111"}, 422),
    ({"amount": -100, "receipt_code": "PT-112"}, 422),
    ({"amount": 1000.5, "receipt_code": "PT-113"}, 422),
    ({"amount": 1000.0, "receipt_code": "PT-113b"}, 422),
    ({"amount": "1000", "receipt_code": "PT-114"}, 422),
    ({"amount": None, "receipt_code": "PT-115"}, 422),
    ({"amount": True, "receipt_code": "PT-116"}, 422),
    ({"amount": 500, "receipt_code": "PT-117"}, 422), # < min
    ({"amount": 25000000, "receipt_code": "PT-118"}, 422), # > max
    ({"amount": 50000, "receipt_code": ""}, 422),
    ({"amount": 50000, "receipt_code": "PT"}, 422), # < 3
    ({"amount": 50000, "receipt_code": "A"*51}, 422), # > 50
    ({"amount": 50000, "receipt_code": "PT-@#$%"}, 422), # ký tự lạ
    ({"amount": 50000, "receipt_code": "PT-119", "note": "A"*201}, 201), # note sẽ bị cắt 200, nhưng 201 thành công (nếu cắt bằng [:200])
])
def test_ac4_validation(payload, expected_status: int) -> None:
    """AC4: validate input"""
    if expected_status == 422 and payload.get("amount") in ["1000", True, 1000.0]:
        # Pydantic auto-casts these to int if possible unless strict=True.
        # Strict mode isn't explicitly requested, but our service checks type(amount) is int and not float
        pass
        
    resp = client.post(
        "/api/wallet/admin/wallets/10/manual-topups",
        json=payload
    )
    assert resp.status_code == expected_status
    if expected_status != 201:
        db = TestingSessionLocal()
        count = db.query(WalletLedgerEntry).filter_by(receipt_code=payload.get("receipt_code")).count()
        assert count == 0
        db.close()


def test_ac4_driver_not_found() -> None:
    resp = client.post(
        "/api/wallet/admin/wallets/999/manual-topups",
        json={"amount": 500000, "receipt_code": "PT-999"}
    )
    assert resp.status_code == 404


def test_ac5_audit_log_created() -> None:
    """AC5: có đúng một dòng nhật ký"""
    resp = client.post(
        "/api/wallet/admin/wallets/10/manual-topups",
        json={"amount": 500000, "receipt_code": "PT-AUDIT"}
    )
    assert resp.status_code == 201
    db = TestingSessionLocal()
    from app.models.audit_log import AuditLog
    audit = db.query(AuditLog).filter_by(action="wallet.manual_topup").first()
    assert audit is not None
    assert audit.actor_id == 1
    assert audit.details["amount_vnd"] == 500000
    assert audit.details["receipt_code"] == "PT-AUDIT"
    db.close()


@pytest.mark.asyncio
async def test_ac6_concurrent_topups() -> None:
    """AC6: nạp tay đồng thời"""
    from httpx import AsyncClient, ASGITransport
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        req1 = ac.post("/api/wallet/admin/wallets/10/manual-topups", json={"amount": 100000, "receipt_code": "CONCUR-1"})
        req2 = ac.post("/api/wallet/admin/wallets/10/manual-topups", json={"amount": 200000, "receipt_code": "CONCUR-2"})
        responses = await asyncio.gather(req1, req2)
    
    assert responses[0].status_code == 201
    assert responses[1].status_code == 201
    
    db = TestingSessionLocal()
    assert wallet_balance_matches_ledger(db, 10) is True
    from app.services.wallet import wallet_totals
    assert wallet_totals(db, 10)["balance_vnd"] == 300000
    db.close()


def test_atomic_rollback_on_audit_fail(monkeypatch) -> None:
    """Giả lập lỗi ở bước ghi nhật ký -> rollback toàn bộ"""
    def mock_append_audit(*args, **kwargs):
        raise ValueError("Simulated DB fail")
        
    import app.services.wallet
    monkeypatch.setattr(app.services.wallet, "append_audit", mock_append_audit)
    
    resp = client.post(
        "/api/wallet/admin/wallets/10/manual-topups",
        json={"amount": 500000, "receipt_code": "PT-ROLLBACK"}
    )
    assert resp.status_code == 422 # Because ValueError is caught by the router!
    
    db = TestingSessionLocal()
    count = db.query(WalletLedgerEntry).filter_by(receipt_code="PT-ROLLBACK").count()
    assert count == 0
    assert wallet_balance_matches_ledger(db, 10) is True
    db.close()


def test_trigger_append_only() -> None:
    """Thử UPDATE và DELETE trực tiếp một dòng wallet_ledger bằng SQL -> bị trigger chặn"""
    db = TestingSessionLocal()
    entry = WalletLedgerEntry(
        user_id=10,
        entry_type="manual_topup",
        amount_vnd=50000,
        idempotency_key="trigger-test",
        receipt_code="PT-TRIGGER",
        description="Test",
        actor_id=1
    )
    db.add(entry)
    db.commit()
    
    with pytest.raises(Exception) as exc:
        db.execute(text("UPDATE wallet_ledger SET amount_vnd = 100000 WHERE id = :id"), {"id": entry.id})
        db.commit()
    assert "append-only" in str(exc.value)
    db.rollback()
    
    with pytest.raises(Exception) as exc:
        db.execute(text("DELETE FROM wallet_ledger WHERE id = :id"), {"id": entry.id})
        db.commit()
    assert "append-only" in str(exc.value)
    db.rollback()
    db.close()


def test_db_constraints() -> None:
    """Ràng buộc DB: chèn thẳng 2 dòng cùng receipt_code; amount = 0"""
    db = TestingSessionLocal()
    entry1 = WalletLedgerEntry(
        user_id=10,
        entry_type="manual_topup",
        amount_vnd=50000,
        idempotency_key="c1",
        receipt_code="PT-CONST",
        description="Test"
    )
    db.add(entry1)
    db.commit()
    
    entry2 = WalletLedgerEntry(
        user_id=10,
        entry_type="manual_topup",
        amount_vnd=50000,
        idempotency_key="c2",
        receipt_code="PT-CONST", # Cùng receipt code (unique)
        description="Test"
    )
    db.add(entry2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    
    # Amount = 0
    entry3 = WalletLedgerEntry(
        user_id=10,
        entry_type="manual_topup",
        amount_vnd=0, # Vi phạm check constraint ck_wallet_ledger_amount_sign
        idempotency_key="c3",
        receipt_code="PT-CONST-3",
        description="Test"
    )
    db.add(entry3)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()
