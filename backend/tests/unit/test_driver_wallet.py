"""Tests for driver wallet read endpoints."""

import asyncio
from datetime import datetime, UTC, timedelta
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.user import Role, User
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.wallet import wallet_totals

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
    def __init__(self, user_id: int, roles: list[str]) -> None:
        self.id = user_id
        self.roles = [MockRole(r) for r in roles]
        self.full_name = f"User {user_id}"

@pytest.fixture(autouse=True)
def setup_database() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=engine_test)
    app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    role_driver = Role(id=1, name="driver")
    role_admin = Role(id=2, name="admin")
    driver_a = User(id=10, email="driverA@demo.vn", password_hash="hashed", full_name="Driver A", is_active=True)
    driver_b = User(id=11, email="driverB@demo.vn", password_hash="hashed", full_name="Driver B", is_active=True)
    driver_no_wallet = User(id=12, email="driverC@demo.vn", password_hash="hashed", full_name="Driver C", is_active=True)
    db.add_all([driver_a, driver_b, driver_no_wallet, role_driver, role_admin])
    db.commit()

    # Thêm 120 dòng cho driver A (user_id=10)
    base_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=200)
    entries = []
    for i in range(120):
        t_type = "manual_topup" if i % 2 == 0 else "session_charge"
        amount = 50000 if i % 2 == 0 else -10000
        desc = f"Desc {i}"
        ref_id = i if t_type == "session_charge" else None
        ref_type = "charging_session" if t_type == "session_charge" else None
        receipt = f"PT-{i}" if t_type == "manual_topup" else None
        
        entries.append(WalletLedgerEntry(
            user_id=10,
            entry_type=t_type,
            amount_vnd=amount,
            description=desc,
            reference_type=ref_type,
            reference_id=ref_id,
            receipt_code=receipt,
            created_at=base_time + timedelta(days=i), # spread over 120 days
            idempotency_key=f"ik-{10}-{i}"
        ))
    
    # Driver B có 1 dòng (ví âm)
    entries.append(WalletLedgerEntry(
        user_id=11,
        entry_type="adjustment",
        amount_vnd=-5000,
        description="Nợ",
        created_at=base_time,
        idempotency_key="ik-11-0"
    ))
    db.add_all(entries)
    db.commit()
    db.close()

    app.dependency_overrides[get_current_user] = lambda: MockUser(user_id=10, roles=["driver"])

    yield

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine_test)


def test_ac1_driver_a_wallet_and_ledger() -> None:
    # Check /api/wallet
    resp = client.get("/api/wallet")
    assert resp.status_code == 200
    data = resp.json()
    assert data["account_id"] == "W-000010"
    assert data["balance_vnd"] == (60 * 50000) - (60 * 10000) # 2.400.000
    assert data["total_topup_vnd"] == 60 * 50000
    assert data["total_spent_vnd"] == 60 * 10000
    assert "as_of" in data

    # Check /api/wallet/ledger
    resp2 = client.get("/api/wallet/ledger")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total"] == 120
    assert len(data2["items"]) == 50 # default page_size
    assert data2["items"][0]["created_at"].endswith("Z")
    assert data2["items"][0]["type"] in ("topup", "charge", "adjustment")
    # Verify no personal info
    for item in data2["items"]:
        assert "email" not in item
        assert "note" not in item
        assert "actor_user_id" not in item


def test_ac2_authorization_driver_b() -> None:
    # A đang đăng nhập (user_id=10), cố truy cập ví của B (user_id=11)
    resp = client.get("/api/wallets/11")
    assert resp.status_code == 403
    resp2 = client.get("/api/wallets/11/ledger")
    assert resp2.status_code == 403

    # Truy cập ID không tồn tại
    resp3 = client.get("/api/wallets/999")
    assert resp3.status_code == 403

    # Gọi id của chính mình
    resp4 = client.get("/api/wallets/10")
    assert resp4.status_code == 200

    # Test cố tình truyền query param (user_id=B) vào api/wallet -> bị bỏ qua
    resp5 = client.get("/api/wallet?user_id=11&wallet_id=11")
    assert resp5.status_code == 200
    assert resp5.json()["account_id"] == "W-000010"


def test_ac3_no_wallet() -> None:
    app.dependency_overrides[get_current_user] = lambda: MockUser(user_id=12, roles=["driver"])
    resp = client.get("/api/wallet")
    assert resp.status_code == 200
    data = resp.json()
    assert data["balance_vnd"] == 0
    assert data["total_topup_vnd"] == 0
    assert data["total_spent_vnd"] == 0

    resp2 = client.get("/api/wallet/ledger")
    assert resp2.status_code == 200
    assert resp2.json()["total"] == 0
    assert len(resp2.json()["items"]) == 0
    
    # Kiểm tra database không sinh thêm dòng
    db = TestingSessionLocal()
    count = db.query(WalletLedgerEntry).filter_by(user_id=12).count()
    assert count == 0
    db.close()


@pytest.mark.parametrize("role", ["admin", "accountant", "operator", "station_owner"])
def test_ac4_other_roles(role: str) -> None:
    app.dependency_overrides[get_current_user] = lambda: MockUser(user_id=1, roles=[role])
    resp = client.get("/api/wallet")
    assert resp.status_code == 403

def test_ac4_unauthorized() -> None:
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    resp = client.get("/api/wallet")
    assert resp.status_code == 401


def test_ac5_pagination_and_filters() -> None:
    # Page 1
    resp = client.get("/api/wallet/ledger?page=1&page_size=50")
    assert len(resp.json()["items"]) == 50
    # Page 2
    resp2 = client.get("/api/wallet/ledger?page=2&page_size=50")
    assert len(resp2.json()["items"]) == 50
    # Page 3
    resp3 = client.get("/api/wallet/ledger?page=3&page_size=50")
    assert len(resp3.json()["items"]) == 20
    
    # Check limit 50
    resp4 = client.get("/api/wallet/ledger?page=1&page_size=200")
    assert len(resp4.json()["items"]) == 50
    assert resp4.json()["page_size"] == 50
    
    # Lọc days
    resp_days = client.get("/api/wallet/ledger?days=30")
    assert resp_days.status_code == 200
    # Invalid days
    resp_inv = client.get("/api/wallet/ledger?days=abc")
    assert resp_inv.status_code == 422
    
    # Negative page
    resp_neg = client.get("/api/wallet/ledger?page=-1")
    assert resp_neg.status_code == 422


def test_no_writes(monkeypatch) -> None:
    db = TestingSessionLocal()
    # Mock db.execute to raise Exception on non-SELECT
    original_execute = db.execute
    def mock_execute(statement, *args, **kwargs):
        sql_str = str(statement).upper()
        if any(kw in sql_str for kw in ["INSERT", "UPDATE", "DELETE"]):
            raise Exception("Read-only violation!")
        return original_execute(statement, *args, **kwargs)
    
    monkeypatch.setattr(db, "execute", mock_execute)
    
    app.dependency_overrides[get_db] = lambda: db
    resp = client.get("/api/wallet")
    assert resp.status_code == 200
    resp2 = client.get("/api/wallet/ledger")
    assert resp2.status_code == 200
    db.close()
