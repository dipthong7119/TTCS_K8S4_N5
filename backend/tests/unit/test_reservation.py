import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from unittest import mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.deps import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.charge_point import ChargePoint, Connector
from app.models.id_tag import IdTag
from app.models.ocpp_message import OcppMessage  # noqa: F401
from app.models.reservation import Reservation
from app.models.station import Station
from app.models.user import Role, User, user_roles
from app.models.wallet_ledger import WalletLedgerEntry
from app.schemas.reservation import ReservationCreateRequest
from app.services.connection_manager import manager
from app.services.reservation import create_reservation

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
    def __init__(self, user_id: int, roles: list[str], email: str = "driver@test.com"):
        self.id = user_id
        self.email = email
        self.full_name = "Driver Test"
        self.roles = [MockRole(r) for r in roles]


user_by_thread = threading.local()


def get_mock_user():
    user_id = getattr(user_by_thread, "user_id", 10)
    roles = getattr(user_by_thread, "roles", ["driver"])
    return MockUser(user_id, roles)



@pytest.fixture(scope="function", autouse=True)
def setup_db():
    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine_test)
    Base.metadata.create_all(bind=engine_test)

    db = SessionLocalTest()

    # Tạo roles
    r_driver = Role(id=1, name="driver")
    r_admin = Role(id=2, name="admin")
    db.add_all([r_driver, r_admin])

    # Tạo users
    user_driver = User(
        id=10,
        email="driver@test.com",
        password_hash="hashed",
        full_name="Driver Test",
        is_active=True,
    )
    user_other = User(
        id=20,
        email="other@test.com",
        password_hash="hashed",
        full_name="Other Driver",
        is_active=True,
    )
    db.add_all([user_driver, user_other])
    db.flush()

    # Gán role driver
    db.execute(
        user_roles.insert().values(
            [
                {"user_id": 10, "role_id": 1},
                {"user_id": 20, "role_id": 1},
            ]
        )
    )

    # Nạp số dư ví cho driver (100,000 VND)
    wallet_entry = WalletLedgerEntry(
        user_id=10,
        amount_vnd=100000,
        entry_type="manual_topup",
        idempotency_key="init_topup_10",
        description="Initial topup for test",
    )
    db.add(wallet_entry)

    # Thẻ sạc của driver
    tag = IdTag(
        id=1,
        user_id=10,
        id_tag="TAG-DRIVER-10",
        is_virtual=True,
        is_blocked=False,
    )
    db.add(tag)

    # Trạm và Trụ sạc
    station = Station(id=1, name="Station Test", owner_id=10, status="active")
    point = ChargePoint(
        id=1,
        code="CP_TEST_01",
        station_id=1,
        status="online",
        last_seen_at=datetime.now(UTC).replace(tzinfo=None),
    )
    conn1 = Connector(
        id=1,
        charge_point_id=1,
        connector_id=1,
        status="available",
        ocpp_status="Available",
    )
    conn2 = Connector(
        id=2,
        charge_point_id=1,
        connector_id=2,
        status="charging",
        ocpp_status="Charging",
    )
    db.add_all([station, point, conn1, conn2])
    db.commit()
    db.close()

    # Mặc định đăng nhập user 10 (role driver)
    user_by_thread.user_id = 10
    user_by_thread.roles = ["driver"]
    app.dependency_overrides[get_current_user] = get_mock_user

    yield

    Base.metadata.drop_all(bind=engine_test)
    manager.active_connections.clear()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous_overrides)


def test_create_reservation_success_accepted(monkeypatch):
    """AC 1: Trụ online, connector available, ví đủ số dư, ReserveNow Accepted -> đặt chỗ thành công và connector đổi sang reserved."""
    monkeypatch.setitem(manager.active_connections, "CP_TEST_01", mock.AsyncMock())

    async def fake_send_call(code, action, payload, timeout):
        assert code == "CP_TEST_01"
        assert action == "ReserveNow"
        assert payload["connectorId"] == 1
        assert payload["idTag"] == "TAG-DRIVER-10"
        assert "reservationId" in payload
        assert "expiryDate" in payload
        return {"status": "Accepted"}

    monkeypatch.setattr(manager, "send_call", fake_send_call)

    resp = client.post(
        "/api/reservations",
        json={
            "charge_point_code": "CP_TEST_01",
            "connector_id": 1,
            "expiry_minutes": 30,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "Accepted"
    assert "Đặt chỗ thành công" in data["message"]
    assert data["reservation"]["status"] == "accepted"
    assert data["reservation"]["connector_id"] == 1
    assert data["reservation"]["id_tag"] == "TAG-DRIVER-10"

    # Kiểm tra DB: connector phải chuyển sang reserved
    db = SessionLocalTest()
    conn = db.query(Connector).filter(Connector.id == 1).first()
    assert conn.status == "reserved"
    assert conn.ocpp_status == "Reserved"

    # Kiểm tra reservation trong DB
    res = db.query(Reservation).filter(Reservation.id == data["reservation"]["id"]).first()
    assert res.status == "accepted"
    assert res.reject_reason is None
    db.close()


def test_create_reservation_charge_point_offline(monkeypatch):
    """Trụ offline hoặc mất kết nối websocket -> trả 409 Conflict."""
    db = SessionLocalTest()
    point = db.query(ChargePoint).filter(ChargePoint.code == "CP_TEST_01").first()
    point.status = "offline"
    db.commit()
    db.close()

    resp = client.post(
        "/api/reservations",
        json={
            "charge_point_code": "CP_TEST_01",
            "connector_id": 1,
            "expiry_minutes": 30,
        },
    )
    assert resp.status_code == 409
    assert "ngoại tuyến" in resp.json()["detail"]


def test_create_reservation_connector_busy(monkeypatch):
    """Đầu nối đang bận (status=charging) -> trả 409 Conflict."""
    monkeypatch.setitem(manager.active_connections, "CP_TEST_01", mock.AsyncMock())

    resp = client.post(
        "/api/reservations",
        json={
            "charge_point_code": "CP_TEST_01",
            "connector_id": 2,  # conn2 đang charging
            "expiry_minutes": 30,
        },
    )
    assert resp.status_code == 409
    assert "Đầu nối đang bận" in resp.json()["detail"]


def test_create_reservation_insufficient_wallet(monkeypatch):
    """Số dư ví dưới ngưỡng tối thiểu (50k) -> trả 400 Bad Request."""
    monkeypatch.setitem(manager.active_connections, "CP_TEST_01", mock.AsyncMock())

    # Trừ ví tài xế xuống 0
    db = SessionLocalTest()
    debit = WalletLedgerEntry(
        user_id=10,
        amount_vnd=-100000,
        entry_type="session_charge",
        idempotency_key="debit_test_10",
        description="Debit for test",
    )
    db.add(debit)
    db.commit()
    db.close()

    resp = client.post(
        "/api/reservations",
        json={
            "charge_point_code": "CP_TEST_01",
            "connector_id": 1,
            "expiry_minutes": 30,
        },
    )
    assert resp.status_code == 400
    assert "Số dư ví không đủ ngưỡng tối thiểu" in resp.json()["detail"]


def test_create_reservation_invalid_time_window(monkeypatch):
    """Thời gian đặt trong quá khứ hoặc quá 2 giờ tới -> trả 422 Unprocessable Entity."""
    monkeypatch.setitem(manager.active_connections, "CP_TEST_01", mock.AsyncMock())

    past_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    resp = client.post(
        "/api/reservations",
        json={
            "charge_point_code": "CP_TEST_01",
            "connector_id": 1,
            "start_time": past_time,
        },
    )
    assert resp.status_code == 422
    assert "không được ở trong quá khứ" in resp.json()["detail"]

    far_future = (datetime.now(UTC) + timedelta(hours=3)).isoformat()
    resp2 = client.post(
        "/api/reservations",
        json={
            "charge_point_code": "CP_TEST_01",
            "connector_id": 1,
            "start_time": far_future,
        },
    )
    assert resp2.status_code == 422
    assert "trong vòng 2 giờ tới" in resp2.json()["detail"]


def test_create_reservation_charge_point_rejected(monkeypatch):
    """Trụ phản hồi Occupied hoặc Rejected -> trả 409, lưu reject_reason trong DB."""
    monkeypatch.setitem(manager.active_connections, "CP_TEST_01", mock.AsyncMock())

    async def fake_send_call(code, action, payload, timeout):
        return {"status": "Occupied"}

    monkeypatch.setattr(manager, "send_call", fake_send_call)

    resp = client.post(
        "/api/reservations",
        json={
            "charge_point_code": "CP_TEST_01",
            "connector_id": 1,
            "expiry_minutes": 30,
        },
    )
    assert resp.status_code == 409
    assert "Occupied" in resp.json()["detail"]

    # Kiểm tra DB: reservation lưu rejected
    db = SessionLocalTest()
    res = db.query(Reservation).order_by(Reservation.id.desc()).first()
    assert res.status == "rejected"
    assert res.reject_reason == "Occupied"
    db.close()


def test_create_reservation_timeout(monkeypatch):
    """Trụ timeout khi gửi ReserveNow -> trả 504 Gateway Timeout."""
    monkeypatch.setitem(manager.active_connections, "CP_TEST_01", mock.AsyncMock())

    async def fake_send_call(code, action, payload, timeout):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(manager, "send_call", fake_send_call)

    resp = client.post(
        "/api/reservations",
        json={
            "charge_point_code": "CP_TEST_01",
            "connector_id": 1,
            "expiry_minutes": 30,
        },
    )
    assert resp.status_code == 504
    assert "thời gian chờ" in resp.json()["detail"]


def test_create_reservation_conflict_existing_reservation(monkeypatch):
    """Đầu nối đã có đặt chỗ hợp lệ đang active -> trả 409 Conflict."""
    monkeypatch.setitem(manager.active_connections, "CP_TEST_01", mock.AsyncMock())

    # Tạo sẵn 1 active reservation
    db = SessionLocalTest()
    active_res = Reservation(
        charge_point_id=1,
        connector_id=1,
        user_id=20,
        id_tag="TAG-OTHER",
        start_time=datetime.now(UTC).replace(tzinfo=None),
        expiry_date=(datetime.now(UTC) + timedelta(minutes=45)).replace(tzinfo=None),
        status="accepted",
    )
    db.add(active_res)
    db.commit()
    db.close()

    resp = client.post(
        "/api/reservations",
        json={
            "charge_point_code": "CP_TEST_01",
            "connector_id": 1,
            "expiry_minutes": 30,
        },
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "Đầu nối đã có người đặt trước" in detail["message"]
    assert detail["code"] == "connector_already_reserved"
    assert "suggestions" in detail


def test_list_and_get_user_reservations(monkeypatch):
    """Tài xế xem danh sách đặt chỗ của mình và chi tiết theo ID; bị chặn khi xem của tài xế khác."""
    db = SessionLocalTest()
    res1 = Reservation(
        id=101,
        charge_point_id=1,
        connector_id=1,
        user_id=10,
        id_tag="TAG-DRIVER-10",
        start_time=datetime.now(UTC).replace(tzinfo=None),
        expiry_date=(datetime.now(UTC) + timedelta(minutes=30)).replace(tzinfo=None),
        status="accepted",
    )
    res2 = Reservation(
        id=102,
        charge_point_id=1,
        connector_id=2,
        user_id=20,  # tài xế khác
        id_tag="TAG-OTHER",
        start_time=datetime.now(UTC).replace(tzinfo=None),
        expiry_date=(datetime.now(UTC) + timedelta(minutes=30)).replace(tzinfo=None),
        status="accepted",
    )
    db.add_all([res1, res2])
    db.commit()
    db.close()

    # User 10 gọi list/me -> chỉ thấy res1
    resp = client.get("/api/reservations/me")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["id"] == 101
    assert items[0]["charge_point_code"] == "CP_TEST_01"

    # User 10 gọi detail res1 -> 200
    resp_detail = client.get("/api/reservations/101")
    assert resp_detail.status_code == 200
    assert resp_detail.json()["id"] == 101

    # User 10 gọi detail res2 của người khác -> 403 Forbidden
    resp_forbidden = client.get("/api/reservations/102")
    assert resp_forbidden.status_code == 403


def test_db_partial_unique_constraint_blocks_concurrent_active_reservations():
    """Ràng buộc CSDL (partial unique index uq_reservations_active_connector) chặn 2 reservation active."""
    db = SessionLocalTest()
    now = datetime.now(UTC).replace(tzinfo=None)

    res1 = Reservation(
        charge_point_id=1,
        connector_id=1,
        user_id=10,
        id_tag="TAG-1",
        start_time=now,
        expiry_date=now + timedelta(minutes=30),
        status="pending",
    )
    db.add(res1)
    db.commit()

    # Thêm reservation thứ hai ở trạng thái accepted/pending trên cùng đầu nối -> Bị DB chặn (IntegrityError)
    res2 = Reservation(
        charge_point_id=1,
        connector_id=1,
        user_id=20,
        id_tag="TAG-2",
        start_time=now,
        expiry_date=now + timedelta(minutes=30),
        status="accepted",
    )
    db.add(res2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Thêm reservation ở trạng thái rejected hoặc expired hoặc cancelled -> Cho phép bình thường
    res_rejected = Reservation(
        charge_point_id=1,
        connector_id=1,
        user_id=20,
        id_tag="TAG-2",
        start_time=now,
        expiry_date=now + timedelta(minutes=30),
        status="rejected",
    )
    db.add(res_rejected)
    db.commit()
    assert res_rejected.id is not None
    db.close()


def test_find_alternative_connectors_returns_available_options(monkeypatch):
    """Khi đầu nối bị trùng, trả về danh sách các đầu nối khả dụng cùng trạm hoặc trạm khác (SCRUM-77)."""
    monkeypatch.setitem(manager.active_connections, "CP_TEST_01", mock.AsyncMock())
    monkeypatch.setitem(manager.active_connections, "CP_TEST_02", mock.AsyncMock())

    db = SessionLocalTest()
    # Thêm trụ thứ 2 trong cùng trạm và đầu nối khả dụng
    cp2 = ChargePoint(
        id=2,
        code="CP_TEST_02",
        station_id=1,
        status="online",
        last_seen_at=datetime.now(UTC).replace(tzinfo=None),
    )
    conn2_1 = Connector(
        id=10,
        charge_point_id=2,
        connector_id=1,
        status="available",
        ocpp_status="Available",
    )
    db.add_all([cp2, conn2_1])

    # Đặt trước connector 1 của CP_TEST_01
    active_res = Reservation(
        charge_point_id=1,
        connector_id=1,
        user_id=20,
        id_tag="TAG-OTHER",
        start_time=datetime.now(UTC).replace(tzinfo=None),
        expiry_date=(datetime.now(UTC) + timedelta(minutes=45)).replace(tzinfo=None),
        status="accepted",
    )
    db.add(active_res)
    db.commit()
    db.close()

    resp = client.post(
        "/api/reservations",
        json={
            "charge_point_code": "CP_TEST_01",
            "connector_id": 1,
            "expiry_minutes": 30,
        },
    )
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "suggestions" in detail
    suggestions = detail["suggestions"]
    assert len(suggestions) >= 1
    suggested_codes = [s["charge_point_code"] for s in suggestions]
    assert "CP_TEST_02" in suggested_codes


def test_expired_reservation_allows_new_reservation(monkeypatch):
    """Đặt chỗ cũ đã quá hạn được tự động giải phóng (expired), cho phép tài xế mới đặt thành công."""
    monkeypatch.setitem(manager.active_connections, "CP_TEST_01", mock.AsyncMock())

    async def fake_send_call(code, action, payload, timeout):
        return {"status": "Accepted"}

    monkeypatch.setattr(manager, "send_call", fake_send_call)

    # Tạo reservation đã quá hạn (expiry_date trong quá khứ)
    db = SessionLocalTest()
    past_res = Reservation(
        charge_point_id=1,
        connector_id=1,
        user_id=20,
        id_tag="TAG-OTHER",
        start_time=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
        expiry_date=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=30),
        status="accepted",
    )
    db.add(past_res)
    db.commit()
    past_res_id = past_res.id
    db.close()

    resp = client.post(
        "/api/reservations",
        json={
            "charge_point_code": "CP_TEST_01",
            "connector_id": 1,
            "expiry_minutes": 30,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "Accepted"

    # Kiểm tra reservation cũ đã chuyển sang expired trong CSDL
    db = SessionLocalTest()
    old_res = db.query(Reservation).filter(Reservation.id == past_res_id).first()
    assert old_res.status == "expired"
    db.close()


def test_concurrent_two_drivers_reserve_same_connector_only_one_succeeds(tmp_path, monkeypatch):
    """SCRUM-77 (S-49): Hai tài xế đặt cùng trụ cùng lúc -> chỉ đúng một người thành công, người kia nhận 409 + gợi ý."""
    database = tmp_path / "concurrent_reservation.db"
    concur_engine = create_engine(
        f"sqlite:///{database.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(bind=concur_engine)
    factory = sessionmaker(bind=concur_engine, expire_on_commit=False)

    with factory() as seed_db:
        r_driver = Role(id=1, name="driver")
        u10 = User(id=10, email="d10@test.com", password_hash="h", full_name="Driver 10", is_active=True)
        u10.roles = [r_driver]
        u20 = User(id=20, email="d20@test.com", password_hash="h", full_name="Driver 20", is_active=True)
        u20.roles = [r_driver]
        w10 = WalletLedgerEntry(user_id=10, amount_vnd=100000, entry_type="manual_topup", idempotency_key="top10", description="Topup 10")
        w20 = WalletLedgerEntry(user_id=20, amount_vnd=100000, entry_type="manual_topup", idempotency_key="top20", description="Topup 20")
        t10 = IdTag(id=1, user_id=10, id_tag="TAG-10", is_virtual=True, is_blocked=False)
        t20 = IdTag(id=2, user_id=20, id_tag="TAG-20", is_virtual=True, is_blocked=False)
        st = Station(id=1, name="Station Test", owner_id=10, status="active")
        cp = ChargePoint(id=1, code="CP_CONCUR_01", station_id=1, status="online", last_seen_at=datetime.now(UTC).replace(tzinfo=None))
        conn = Connector(id=1, charge_point_id=1, connector_id=1, status="available", ocpp_status="Available")
        seed_db.add_all([r_driver, u10, u20, w10, w20, t10, t20, st, cp, conn])
        seed_db.commit()

    monkeypatch.setitem(manager.active_connections, "CP_CONCUR_01", mock.AsyncMock())

    async def fake_send_call(code, action, payload, timeout):
        await asyncio.sleep(0.05)
        return {"status": "Accepted"}

    monkeypatch.setattr(manager, "send_call", fake_send_call)

    barrier = Barrier(2)
    results = []

    def run_driver(user_id: int):
        with factory() as db:
            barrier.wait(timeout=5)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                user = db.get(User, user_id)
                payload = ReservationCreateRequest(
                    charge_point_code="CP_CONCUR_01",
                    connector_id=1,
                    expiry_minutes=30,
                )
                res = loop.run_until_complete(create_reservation(db, user, payload))
                results.append((user_id, 201, res.model_dump()))
            except HTTPException as exc:
                results.append((user_id, exc.status_code, exc.detail))
            finally:
                loop.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_driver, uid) for uid in [10, 20]]
        for f in futures:
            f.result()

    # Đúng 1 người nhận 201 Created và 1 người nhận 409 Conflict
    status_codes = [r[1] for r in results]
    assert sorted(status_codes) == [201, 409]

    success = next(r[2] for r in results if r[1] == 201)
    assert success["status"] == "Accepted"
    assert success["reservation"] is not None

    fail = next(r[2] for r in results if r[1] == 409)
    assert "Đầu nối đã có người đặt trước" in fail["message"]
    assert "suggestions" in fail

    # Kiểm tra trong DB chỉ có đúng 1 reservation active
    with factory() as db:
        active_res = (
            db.query(Reservation)
            .filter(
                Reservation.charge_point_id == 1,
                Reservation.connector_id == 1,
                Reservation.status == "accepted",
            )
            .all()
        )
        assert len(active_res) == 1
    concur_engine.dispose()


