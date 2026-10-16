"""Kiểm thử S-51: Tài xế huỷ chỗ đã đặt và trụ mở lại cho người khác.

Bao gồm:
- AC1: Huỷ chỗ active trước hạn thành công (200, status=cancelled, cancel_status=done), không trừ ví, gửi CancelReservation 1 lần.
- Trụ gửi StatusNotification Reserved -> Available cập nhật connector.
- Trụ trả Rejected -> cancel_status='gone', ghi log cảnh báo.
- Trụ offline/timeout -> cancel_status='pending', huỷ vẫn thành công 200.
- Idempotency: gọi huỷ lần 2 không gửi thêm CancelReservation.
- Đặt chỗ đã expired -> 409 RESERVATION_EXPIRED.
- Đặt chỗ quá hạn (now >= expiry_at) nhưng job chưa quét -> 409 RESERVATION_EXPIRED.
- Đặt chỗ đã fulfilled -> 409 RESERVATION_FULFILLED.
- Quá thời hạn cutoff (CANCEL_CUTOFF_SECONDS) -> 409 CANCEL_TOO_LATE.
- Đặt chỗ của người khác -> 403 Forbidden.
- Đặt chỗ không tồn tại -> 403 Forbidden (thống nhất chống enumeration).
- Chưa đăng nhập -> 401.
- Sai vai trò (không phải driver) -> 403.
- Kiểm thử đua tranh giữa huỷ và job hết hạn / hai lần gọi huỷ đồng thời.
- Kiểm tra không rò rỉ PII trong log và audit log.
- Job thử lại xử lý các đặt chỗ cancelled đang pending, chuyển sang abandoned khi quá số lần.
"""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.core.deps import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.charge_point import ChargePoint, Connector
from app.models.id_tag import IdTag
from app.models.reservation import CancelStatus, Reservation, ReservationStatus
from app.models.station import Station
from app.models.user import Role, User
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.connection_manager import manager
from app.services.reservation_job import _abandon_stale_cancels, retry_cancel_reservations_once
from app.services.reservations import (
    ReservationCancelError,
    cancel_reservation,
    expire_reservation,
)


@pytest.fixture
def test_env(tmp_path: Path):
    """Môi trường kiểm thử cô lập với SQLite tạm."""
    db_path = tmp_path / "test_s51.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    conn = engine.connect()
    conn.execute(text("PRAGMA foreign_keys=ON"))
    conn.close()

    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    db = TestSession()

    # Dữ liệu nền: roles
    role_driver = Role(name="driver")
    role_owner = Role(name="station_owner")
    role_operator = Role(name="operator")
    db.add_all([role_driver, role_owner, role_operator])
    db.flush()

    # Users
    driver_a = User(email="driver_a@x.com", password_hash="x", full_name="Driver A")
    driver_a.roles = [role_driver]

    driver_b = User(email="driver_b@x.com", password_hash="x", full_name="Driver B")
    driver_b.roles = [role_driver]

    owner = User(email="owner@x.com", password_hash="x", full_name="Station Owner")
    owner.roles = [role_owner]

    operator = User(email="operator@x.com", password_hash="x", full_name="Operator")
    operator.roles = [role_operator]

    db.add_all([driver_a, driver_b, owner, operator])
    db.flush()

    # Station, ChargePoint, Connector
    station = Station(
        name="Trạm Kiểm Thử S51",
        owner_id=owner.id,
        status="active",
        no_show_fee_vnd=25_000,
    )
    db.add(station)
    db.flush()

    cp = ChargePoint(
        code="CP-S51-01",
        station_id=station.id,
        status="online",
        last_seen_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(cp)
    db.flush()

    connector = Connector(
        charge_point_id=cp.id,
        connector_id=1,
        status="reserved",
        ocpp_status="Reserved",
    )
    db.add(connector)
    db.flush()

    tag_a = IdTag(id_tag="TAG-DRV-A", user_id=driver_a.id, is_virtual=False, is_blocked=False)
    tag_b = IdTag(id_tag="TAG-DRV-B", user_id=driver_b.id, is_virtual=False, is_blocked=False)
    db.add_all([tag_a, tag_b])
    db.flush()

    # Nạp tiền ban đầu cho Driver A: 100_000 đ
    entry = WalletLedgerEntry(
        user_id=driver_a.id,
        entry_type="manual_topup",
        amount_vnd=100_000,
        idempotency_key=f"init-topup:{driver_a.id}",
        description="Topup 100k",
    )
    db.add(entry)
    db.commit()

    users = {
        "driver_a": driver_a,
        "driver_b": driver_b,
        "owner": owner,
        "operator": operator,
    }

    def override_get_db() -> Generator[Session, None, None]:
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: users["driver_a"]

    client = TestClient(app)

    yield {
        "client": client,
        "db": db,
        "engine": engine,
        "users": users,
        "cp": cp,
        "connector": connector,
        "tag_a": tag_a,
        "tag_b": tag_b,
        "station": station,
        "TestSession": TestSession,
    }

    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def make_active_res(
    db: Session,
    env: dict,
    driver: User,
    expiry_offset_seconds: int = 1800,  # 30 phút trong tương lai
    fee_vnd: int | None = 25_000,
) -> Reservation:
    """Tạo reservation active."""
    now = datetime.now(UTC).replace(tzinfo=None)
    connector = env["connector"]
    tag = (
        env["tag_a"]
        if driver.id == env["users"]["driver_a"].id
        else env["tag_b"]
    )
    res = Reservation(
        charge_point_id=env["cp"].id,
        connector_db_id=connector.id,
        driver_user_id=driver.id,
        connector_id=connector.connector_id,
        id_tag=tag.id_tag,
        id_tag_id=tag.id,
        start_time=now - timedelta(minutes=30),
        status=ReservationStatus.ACTIVE,
        expiry_at=now + timedelta(seconds=expiry_offset_seconds),
        no_show_fee_vnd=fee_vnd,
        cancel_status=CancelStatus.PENDING,
    )
    db.add(res)
    db.commit()
    db.refresh(res)
    return res


def get_wallet_balance(db: Session, user_id: int) -> int:
    """Tính số dư ví từ bảng sổ cái."""
    val = db.query(func.coalesce(func.sum(WalletLedgerEntry.amount_vnd), 0)).filter(
        WalletLedgerEntry.user_id == user_id
    ).scalar()
    return int(val)


# ── AC1: Huỷ chỗ thành công ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac1_cancel_active_reservation_success(test_env, monkeypatch):
    """Tài xế huỷ chỗ active trước hạn thành công qua API."""
    db = test_env["db"]
    client = test_env["client"]
    driver_a = test_env["users"]["driver_a"]
    cp = test_env["cp"]

    monkeypatch.setattr(settings, "CANCEL_CUTOFF_SECONDS", 0)

    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=1800)
    bal_before = get_wallet_balance(db, driver_a.id)

    # Mock manager.send_call trả Accepted
    mock_send = AsyncMock(return_value={"status": "Accepted"})
    monkeypatch.setattr("app.services.reservations.manager.send_call", mock_send)

    resp = client.post(f"/api/reservations/{res.id}/cancel")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == res.id
    assert data["status"] == "cancelled"
    assert data["cancel_status"] == "done"
    assert data["cancelled_at"] is not None

    # Không trừ ví
    bal_after = get_wallet_balance(db, driver_a.id)
    assert bal_after == bal_before

    # Gửi CancelReservation đúng 1 lần tới đúng mã trụ
    mock_send.assert_awaited_once_with(
        cp.code,
        "CancelReservation",
        {"reservationId": res.id},
        timeout=float(settings.OCPP_REMOTE_CALL_TIMEOUT_SECONDS),
    )

    # Kiểm tra DB
    db.expire_all()
    updated_res = db.get(Reservation, res.id)
    assert updated_res.status == ReservationStatus.CANCELLED
    assert updated_res.cancel_status == CancelStatus.DONE
    assert updated_res.fee_waived_reason == "driver_cancelled"

    # Kiểm tra audit log
    audit = db.query(AuditLog).filter_by(action="reservation.cancelled", object_id=res.id).first()
    assert audit is not None
    assert audit.actor_id == driver_a.id
    assert audit.details["fee_waived_reason"] == "driver_cancelled"


@pytest.mark.asyncio
async def test_ac1_cancel_service_directly(test_env, monkeypatch):
    """Gọi trực tiếp service cancel_reservation."""
    db = test_env["db"]
    driver_a = test_env["users"]["driver_a"]

    monkeypatch.setattr(settings, "CANCEL_CUTOFF_SECONDS", 0)

    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=3600)

    mock_send = AsyncMock(return_value={"status": "Accepted"})
    monkeypatch.setattr("app.services.reservations.manager.send_call", mock_send)

    result = await cancel_reservation(db, res.id, driver_a.id)
    assert result["status"] == "cancelled"
    assert result["cancel_status"] == "done"
    assert result["id"] == res.id


# ── Trụ trả Rejected -> gone ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_charger_rejected_becomes_gone(test_env, monkeypatch, caplog):
    """Trụ trả Rejected -> cancel_status='gone' và ghi log warning."""
    db = test_env["db"]
    client = test_env["client"]
    driver_a = test_env["users"]["driver_a"]

    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=1800)

    mock_send = AsyncMock(return_value={"status": "Rejected"})
    monkeypatch.setattr("app.services.reservations.manager.send_call", mock_send)

    with caplog.at_level("WARNING", logger="app.services.reservations"):
        resp = client.post(f"/api/reservations/{res.id}/cancel")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "cancelled"
    assert data["cancel_status"] == "gone"

    # Đảm bảo có log warning về trụ Rejected
    assert any("Rejected" in record.message for record in caplog.records)


# ── Trụ offline / timeout -> pending ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_charger_timeout_becomes_pending(test_env, monkeypatch):
    """Trụ timeout -> huỷ vẫn thành công 200, cancel_status='pending'."""
    db = test_env["db"]
    client = test_env["client"]
    driver_a = test_env["users"]["driver_a"]

    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=1800)

    mock_send = AsyncMock(side_effect=TimeoutError("Connection timed out"))
    monkeypatch.setattr("app.services.reservations.manager.send_call", mock_send)

    resp = client.post(f"/api/reservations/{res.id}/cancel")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "cancelled"
    assert data["cancel_status"] == "pending"

    db.expire_all()
    r = db.get(Reservation, res.id)
    assert r.status == ReservationStatus.CANCELLED
    assert r.cancel_status == CancelStatus.PENDING
    assert r.cancel_attempts == 1


# ── Idempotency: gọi huỷ lần 2 ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_idempotent_cancel_twice(test_env, monkeypatch):
    """Gọi huỷ lần 2 trả 200 dữ liệu cũ, không gửi thêm CancelReservation."""
    db = test_env["db"]
    client = test_env["client"]
    driver_a = test_env["users"]["driver_a"]

    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=1800)

    mock_send = AsyncMock(return_value={"status": "Accepted"})
    monkeypatch.setattr("app.services.reservations.manager.send_call", mock_send)

    resp1 = client.post(f"/api/reservations/{res.id}/cancel")
    assert resp1.status_code == 200
    assert mock_send.await_count == 1

    # Gọi lần 2
    resp2 = client.post(f"/api/reservations/{res.id}/cancel")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["id"] == res.id
    assert data2["status"] == "cancelled"
    assert data2["cancel_status"] == "done"

    # Vẫn chỉ gọi trụ 1 lần duy nhất
    assert mock_send.await_count == 1


# ── 409 RESERVATION_EXPIRED ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_expired_reservation_returns_409(test_env, monkeypatch):
    """Đặt chỗ đã expired (bị tính phí) -> 409 RESERVATION_EXPIRED."""
    db = test_env["db"]
    client = test_env["client"]
    driver_a = test_env["users"]["driver_a"]

    now = datetime.now(UTC).replace(tzinfo=None)
    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=-600)
    expire_reservation(db, res.id, now)

    mock_send = AsyncMock()
    monkeypatch.setattr("app.services.reservations.manager.send_call", mock_send)

    resp = client.post(f"/api/reservations/{res.id}/cancel")
    assert resp.status_code == 409
    data = resp.json()
    assert data["code"] == "RESERVATION_EXPIRED"
    assert "detail" in data
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_ac_overdue_active_reservation_returns_409(test_env, monkeypatch):
    """Đặt chỗ đã quá expiry_at nhưng job chưa quét -> 409 RESERVATION_EXPIRED."""
    db = test_env["db"]
    client = test_env["client"]
    driver_a = test_env["users"]["driver_a"]

    # Đặt chỗ quá hạn 100 giây trước nhưng status vẫn là ACTIVE trong DB
    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=-100)

    mock_send = AsyncMock()
    monkeypatch.setattr("app.services.reservations.manager.send_call", mock_send)

    resp = client.post(f"/api/reservations/{res.id}/cancel")
    assert resp.status_code == 409
    data = resp.json()
    assert data["code"] == "RESERVATION_EXPIRED"
    mock_send.assert_not_called()


# ── 409 RESERVATION_FULFILLED ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_fulfilled_reservation_returns_409(test_env, monkeypatch):
    """Đặt chỗ đã được sử dụng để sạc (fulfilled) -> 409 RESERVATION_FULFILLED."""
    db = test_env["db"]
    client = test_env["client"]
    driver_a = test_env["users"]["driver_a"]

    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=1800)
    res.status = ReservationStatus.FULFILLED
    res.fulfilled_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()

    mock_send = AsyncMock()
    monkeypatch.setattr("app.services.reservations.manager.send_call", mock_send)

    resp = client.post(f"/api/reservations/{res.id}/cancel")
    assert resp.status_code == 409
    data = resp.json()
    assert data["code"] == "RESERVATION_FULFILLED"
    mock_send.assert_not_called()


# ── 409 CANCEL_TOO_LATE ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_cancel_too_late_past_cutoff_returns_409(test_env, monkeypatch):
    """Đã qua mốc CANCEL_CUTOFF_SECONDS -> 409 CANCEL_TOO_LATE."""
    db = test_env["db"]
    client = test_env["client"]
    driver_a = test_env["users"]["driver_a"]

    # Cutoff là 900 giây (15 phút trước khi hết hạn)
    monkeypatch.setattr(settings, "CANCEL_CUTOFF_SECONDS", 900)

    # Đặt chỗ còn 300 giây nữa hết hạn (nằm trong khoảng 15 phút sát giờ)
    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=300)

    mock_send = AsyncMock()
    monkeypatch.setattr("app.services.reservations.manager.send_call", mock_send)

    resp = client.post(f"/api/reservations/{res.id}/cancel")
    assert resp.status_code == 409
    data = resp.json()
    assert data["code"] == "CANCEL_TOO_LATE"
    mock_send.assert_not_called()


# ── 403 / 401 Phân quyền & Sở hữu ───────────────────────────────────────────


def test_ac_other_driver_reservation_returns_403(test_env, monkeypatch):
    """Tài xế khác huỷ reservation của Driver A -> 403 Forbidden."""
    db = test_env["db"]
    client = test_env["client"]
    driver_a = test_env["users"]["driver_a"]
    driver_b = test_env["users"]["driver_b"]

    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=1800)

    # Đổi login sang Driver B
    app.dependency_overrides[get_current_user] = lambda: driver_b

    resp = client.post(f"/api/reservations/{res.id}/cancel")
    assert resp.status_code == 403
    data = resp.json()
    assert data["code"] == "forbidden"

    # Dữ liệu của Driver A không đổi
    db.expire_all()
    r = db.get(Reservation, res.id)
    assert r.status == ReservationStatus.ACTIVE


def test_ac_nonexistent_reservation_returns_403(test_env):
    """Reservation không tồn tại -> 403 Forbidden (chống enumeration)."""
    client = test_env["client"]
    resp = client.post("/api/reservations/999999/cancel")
    assert resp.status_code == 403
    data = resp.json()
    assert data["code"] == "forbidden"


def test_ac_unauthenticated_returns_401(test_env):
    """Chưa đăng nhập -> 401."""
    # Bỏ override login
    app.dependency_overrides.pop(get_current_user, None)
    client = test_env["client"]
    resp = client.post("/api/reservations/1/cancel")
    assert resp.status_code == 401


@pytest.mark.parametrize("role_key", ["owner", "operator"])
def test_ac_non_driver_role_returns_403(test_env, role_key):
    """Vai trò không phải tài xế (chủ trạm, vận hành) -> 403."""
    client = test_env["client"]
    user = test_env["users"][role_key]
    app.dependency_overrides[get_current_user] = lambda: user

    resp = client.post("/api/reservations/1/cancel")
    assert resp.status_code == 403


# ── Đua tranh (Concurrency & Race condition) ─────────────────────────────────


@pytest.mark.asyncio
async def test_ac_race_between_cancel_and_expire(test_env, monkeypatch):
    """Đua giữa huỷ chỗ và job quét quá hạn: chỉ một bên thắng, không bao giờ vừa huỷ vừa bị trừ phí."""
    db = test_env["db"]
    driver_a = test_env["users"]["driver_a"]

    monkeypatch.setattr(settings, "CANCEL_CUTOFF_SECONDS", 0)
    monkeypatch.setattr(settings, "NO_SHOW_GRACE_SECONDS", 0)

    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=-10)
    now = datetime.now(UTC).replace(tzinfo=None)

    # Job hết hạn chạy trước và giành thắng lợi
    ok_expire = expire_reservation(db, res.id, now)
    assert ok_expire is True

    # Tài xế gọi huỷ ngay sau đó
    mock_send = AsyncMock()
    monkeypatch.setattr("app.services.reservations.manager.send_call", mock_send)

    with pytest.raises(ReservationCancelError) as exc_info:
        await cancel_reservation(db, res.id, driver_a.id, now=now)

    assert exc_info.value.code == "RESERVATION_EXPIRED"
    mock_send.assert_not_called()

    # Trạng thái trong DB vẫn là expired
    db.expire_all()
    r = db.get(Reservation, res.id)
    assert r.status == ReservationStatus.EXPIRED


@pytest.mark.asyncio
async def test_ac_two_concurrent_cancel_calls(test_env, monkeypatch):
    """Hai lệnh huỷ gọi liên tiếp/song song: chỉ 1 lần update thắng, trụ chỉ gọi 1 lần."""
    db = test_env["db"]
    driver_a = test_env["users"]["driver_a"]

    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=1800)

    mock_send = AsyncMock(return_value={"status": "Accepted"})
    monkeypatch.setattr("app.services.reservations.manager.send_call", mock_send)

    res1 = await cancel_reservation(db, res.id, driver_a.id)
    res2 = await cancel_reservation(db, res.id, driver_a.id)

    assert res1["status"] == "cancelled"
    assert res2["status"] == "cancelled"
    assert mock_send.await_count == 1


# ── Không rò rỉ PII & Kiểm tra Audit Log ─────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_log_and_audit_no_pii(test_env, monkeypatch, caplog):
    """Log và AuditLog không chứa PII (mã thẻ đầy đủ, số điện thoại, mật khẩu)."""
    db = test_env["db"]
    client = test_env["client"]
    driver_a = test_env["users"]["driver_a"]
    tag_a = test_env["tag_a"]

    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=1800)

    mock_send = AsyncMock(return_value={"status": "Accepted"})
    monkeypatch.setattr("app.services.reservations.manager.send_call", mock_send)

    with caplog.at_level("INFO"):
        resp = client.post(f"/api/reservations/{res.id}/cancel")
    assert resp.status_code == 200

    # Kiểm tra log text
    all_logs = " ".join([r.message for r in caplog.records])
    assert tag_a.id_tag not in all_logs
    assert driver_a.email not in all_logs

    # Kiểm tra audit entry
    audit = db.query(AuditLog).filter_by(action="reservation.cancelled", object_id=res.id).first()
    assert audit is not None
    assert "email" not in audit.details
    assert tag_a.id_tag not in str(audit.details)


# ── Job thử lại cho Cancelled Pending ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_retry_job_processes_pending_cancelled(test_env, monkeypatch):
    """Job thử lại xử lý các đặt chỗ cancelled đang pending."""
    db = test_env["db"]
    driver_a = test_env["users"]["driver_a"]
    now = datetime.now(UTC).replace(tzinfo=None)

    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=1800)
    res.status = ReservationStatus.CANCELLED
    res.cancelled_at = now - timedelta(minutes=10)
    res.cancel_status = CancelStatus.PENDING
    res.cancel_attempts = 1
    db.commit()

    mock_send = AsyncMock(return_value={"status": "Accepted"})
    monkeypatch.setattr("app.services.reservations.manager.send_call", mock_send)

    sent = await retry_cancel_reservations_once(db, now=now)
    assert sent == 1

    db.expire_all()
    r = db.get(Reservation, res.id)
    assert r.cancel_status == CancelStatus.DONE


@pytest.mark.asyncio
async def test_ac_retry_job_abandons_after_max_attempts(test_env, monkeypatch, caplog):
    """Đặt chỗ cancelled hết số lần thử -> abandoned và ghi cảnh báo."""
    db = test_env["db"]
    driver_a = test_env["users"]["driver_a"]
    now = datetime.now(UTC).replace(tzinfo=None)

    monkeypatch.setattr(settings, "CANCEL_RESERVATION_MAX_ATTEMPTS", 3)

    res = make_active_res(db, test_env, driver_a, expiry_offset_seconds=1800)
    res.status = ReservationStatus.CANCELLED
    res.cancelled_at = now - timedelta(minutes=5)
    res.cancel_status = CancelStatus.PENDING
    res.cancel_attempts = 3
    db.commit()

    cutoff = now - timedelta(seconds=settings.CANCEL_RESERVATION_RETRY_WINDOW)

    with caplog.at_level("WARNING"):
        _abandon_stale_cancels(db, now, max_attempts=3, cutoff=cutoff)

    db.expire_all()
    r = db.get(Reservation, res.id)
    assert r.cancel_status == CancelStatus.ABANDONED
    assert any("abandoned" in rec.message for rec in caplog.records)
