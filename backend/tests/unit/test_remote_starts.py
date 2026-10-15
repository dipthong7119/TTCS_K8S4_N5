"""Kiểm thử S-24/T-51 bằng SQLite tạm và trụ OCPP giả."""

import asyncio
import logging
import threading
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core.deps import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.id_tag import IdTag
from app.models.remote_start_request import RemoteStartRequest, RemoteStartStatus
from app.models.station import Station
from app.models.user import Role, User
from app.models.wallet_ledger import WalletLedgerEntry
from app.ocpp.handlers.authorize import handle_authorize
from app.ocpp.handlers.start_transaction import handle_start_transaction
from app.services import remote_start as remote_start_service
from app.services.connection_manager import manager
from app.services.ocpp_parser import OCPPError, parse_message


@pytest.fixture
def context(tmp_path: Path):
    """Tạo database riêng cho test, không chạm csms.db."""
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'remote_start.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)
    db = test_session()
    driver_role = Role(name="driver")
    operator_role = Role(name="operator")
    admin_role = Role(name="admin")
    owner_role = Role(name="station_owner")
    accountant_role = Role(name="accountant")
    owner = User(email="owner@test", password_hash="x", full_name="Owner")
    driver_a = User(email="a@test", password_hash="x", full_name="Driver A")
    driver_b = User(email="b@test", password_hash="x", full_name="Driver B")
    operator = User(email="operator@test", password_hash="x", full_name="Operator")
    admin = User(email="admin@test", password_hash="x", full_name="Admin")
    station_owner = User(email="station-owner@test", password_hash="x", full_name="Station Owner")
    accountant = User(email="accountant@test", password_hash="x", full_name="Accountant")
    driver_a.roles = [driver_role]
    driver_b.roles = [driver_role]
    operator.roles = [operator_role]
    admin.roles = [admin_role]
    station_owner.roles = [owner_role]
    accountant.roles = [accountant_role]
    db.add_all([owner, driver_a, driver_b, operator, admin, station_owner, accountant])
    db.flush()
    for driver in (driver_a, driver_b):
        db.add(
            WalletLedgerEntry(
                user_id=driver.id,
                entry_type="manual_topup",
                amount_vnd=50_000,
                idempotency_key=f"test-start-wallet:{driver.id}",
                description="Test wallet funding",
            )
        )
    station = Station(name="Station", owner_id=owner.id, status="active")
    db.add(station)
    db.flush()
    point = ChargePoint(
        code="CP-REMOTE-1",
        station_id=station.id,
        status="online",
        last_seen_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(point)
    db.flush()
    connector = Connector(
        charge_point_id=point.id,
        connector_id=1,
        status="available",
        ocpp_status="Available",
    )
    db.add(connector)
    db.commit()
    users = {
        "driver_a": driver_a,
        "driver_b": driver_b,
        "operator": operator,
        "admin": admin,
        "station_owner": station_owner,
        "accountant": accountant,
    }
    def override_db() -> Generator[Any, None, None]:
        yield from _yield_session(test_session)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: users["driver_a"]
    manager.active_connections.clear()
    manager.active_connections[point.code] = object()  # type: ignore[assignment]
    client = TestClient(app)
    yield {
        "client": client,
        "db": db,
        "engine": engine,
        "users": users,
        "point": point,
        "connector": connector,
        "station": station,
        "sessions": test_session,
    }
    app.dependency_overrides.clear()
    manager.active_connections.clear()
    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _yield_session(factory: sessionmaker) -> Generator[Any, None, None]:
    db = factory()
    try:
        yield db
    finally:
        db.close()


def _accepting(monkeypatch: pytest.MonkeyPatch, *, status="Accepted", on_call=None):
    calls: list[tuple[str, str, dict, float | None]] = []

    async def send_call(code, action, payload, timeout=None):
        calls.append((code, action, payload, timeout))
        if on_call is not None:
            on_call()
        return {"status": status}

    monkeypatch.setattr(manager, "send_call", send_call)
    return calls


@pytest.mark.parametrize("raw_status", ["Available", "Preparing"])
def test_accepted_then_start_transaction_resolves_same_request(
    raw_status, context, monkeypatch
):
    calls = _accepting(monkeypatch)
    client = context["client"]
    connector = context["connector"]
    connector.ocpp_status = raw_status
    context["db"].commit()

    response = client.post(f"/api/connectors/{connector.id}/remote-start")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "waiting_start"
    assert body["seconds_left"] == settings.REMOTE_START_WAIT
    assert len(calls) == 1
    code, action, payload, timeout = calls[0]
    assert code == "CP-REMOTE-1"
    assert action == "RemoteStartTransaction"
    assert payload["connectorId"] == 1
    assert 1 <= len(payload["idTag"]) <= 20
    assert payload["idTag"].startswith("V")
    assert timeout == settings.REMOTE_START_CALL_TIMEOUT
    assert payload["idTag"] not in response.text

    db = context["db"]
    driver = context["users"]["driver_a"]
    virtual_tags = db.query(IdTag).filter_by(user_id=driver.id, is_virtual=True).all()
    assert len(virtual_tags) == 1
    request_row = db.get(RemoteStartRequest, body["id"])
    assert request_row is not None
    assert request_row.expires_at == request_row.accepted_at + timedelta(
        seconds=settings.REMOTE_START_WAIT
    )
    assert db.query(ChargingSession).count() == 0
    audit_row = db.query(AuditLog).one()
    assert audit_row.actor_id == context["users"]["driver_a"].id
    assert audit_row.actor_email is None
    assert audit_row.actor_name is None
    assert payload["idTag"] not in str(audit_row.details)

    start_payload = {
        "connectorId": 1,
        "idTag": payload["idTag"],
        "meterStart": 1500,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    response_frame = handle_start_transaction(
        db, context["point"], "start-remote-1", start_payload
    )
    assert parse_message(response_frame)[0] == 3
    db.commit()
    db.refresh(request_row)
    assert request_row.status == RemoteStartStatus.STARTED
    assert request_row.session_id is not None

    status = client.get(f"/api/remote-starts/{request_row.id}")
    assert status.status_code == 200
    assert status.json()["status"] == "started"
    assert status.json()["connector_id"] == connector.id
    assert status.json()["session_id"] == request_row.session_id


def test_start_transaction_before_callresult_stays_started(context, monkeypatch):
    async def start_before_result(_code, _action, payload, timeout=None):
        db = context["sessions"]()
        try:
            start_payload = {
                "connectorId": payload["connectorId"],
                "idTag": payload["idTag"],
                "meterStart": 900,
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
            frame = handle_start_transaction(
                db, db.get(ChargePoint, context["point"].id), "early-start", start_payload
            )
            assert parse_message(frame)[0] == 3
            db.commit()
        finally:
            db.close()
        return {"status": "Accepted"}

    monkeypatch.setattr(manager, "send_call", start_before_result)
    response = context["client"].post(
        f"/api/connectors/{context['connector'].id}/remote-start"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "started"
    assert context["db"].query(RemoteStartRequest).one().status == RemoteStartStatus.STARTED


@pytest.mark.parametrize(
    ("raw_status", "has_session"),
    [
        ("Charging", False),
        ("SuspendedEV", False),
        ("SuspendedEVSE", False),
        ("Finishing", False),
        ("Reserved", False),
        ("Unavailable", False),
        ("Faulted", False),
        ("Foo", False),
        ("Available", True),
    ],
)
def test_connector_not_available_never_sends(raw_status, has_session, context, monkeypatch):
    calls = _accepting(monkeypatch)
    connector = context["connector"]
    connector.ocpp_status = raw_status
    context["db"].commit()
    if has_session:
        point = context["point"]
        db = context["db"]
        db.add(
            ChargingSession(
                charge_point_id=point.id,
                charge_point_code=point.code,
                station_id=context["station"].id,
                station_name="Station",
                connector_number=1,
                meter_start_wh=0,
                started_at=datetime.now(UTC).replace(tzinfo=None),
                status="active",
            )
        )
        db.commit()
    response = context["client"].post(f"/api/connectors/{connector.id}/remote-start")
    assert response.status_code == 409
    assert response.json()["code"] == "connector_not_available"
    assert calls == []
    assert context["db"].query(RemoteStartRequest).count() == 0


@pytest.mark.parametrize(
    ("status", "http_code", "stored", "error_code"),
    [
        ("Rejected", 502, RemoteStartStatus.REJECTED, "rejected_by_charger"),
        ("timeout", 504, RemoteStartStatus.NO_REPLY, "charger_timeout"),
        ("callerror", 502, RemoteStartStatus.CHARGER_ERROR, "charger_error"),
    ],
)
def test_charger_failures_are_recorded_and_retryable(
    status, http_code, stored, error_code, context, monkeypatch
):
    calls: list[str] = []
    if status == "timeout":
        async def timeout(*_args, **_kwargs):
            calls.append("timeout")
            raise asyncio.TimeoutError
        monkeypatch.setattr(manager, "send_call", timeout)
    elif status == "callerror":
        async def callerror(*_args, **_kwargs):
            calls.append("callerror")
            raise OCPPError("InternalError", "charger error", {}, "call-1")
        monkeypatch.setattr(manager, "send_call", callerror)
    else:
        calls = _accepting(monkeypatch, status=status)

    response = context["client"].post(
        f"/api/connectors/{context['connector'].id}/remote-start"
    )
    assert response.status_code == http_code
    assert response.json()["code"] == error_code
    if status == "Rejected":
        assert "kiểm tra súng" in response.json()["detail"]
    row = context["db"].query(RemoteStartRequest).one()
    assert row.status == stored
    assert row.expires_at is None
    assert context["db"].query(ChargingSession).count() == 0
    assert context["db"].query(AuditLog).count() == 1
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("change", "expected", "code"),
    [
        ("offline", 409, "charge_point_offline"),
        ("station", 409, "station_suspended"),
        ("missing", 404, "connector_not_found"),
    ],
)
def test_preflight_errors_do_not_send_or_insert(change, expected, code, context, monkeypatch):
    calls = _accepting(monkeypatch)
    if change == "offline":
        context["point"].status = "offline"
        context["db"].commit()
    elif change == "station":
        context["station"].status = "inactive"
        context["db"].commit()
    connector_id = context["connector"].id + 100 if change == "missing" else context["connector"].id
    response = context["client"].post(f"/api/connectors/{connector_id}/remote-start")
    assert response.status_code == expected
    assert response.json()["code"] == code
    assert calls == []
    assert context["db"].query(RemoteStartRequest).count() == 0
    assert context["db"].query(AuditLog).count() == 0


def test_duplicate_driver_request_returns_existing_without_second_command(context, monkeypatch):
    calls = _accepting(monkeypatch)
    endpoint = f"/api/connectors/{context['connector'].id}/remote-start"
    first = context["client"].post(endpoint)
    second = context["client"].post(endpoint)
    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(calls) == 1
    assert context["db"].query(RemoteStartRequest).count() == 1


def test_wait_expiry_uses_configured_duration(context, monkeypatch):
    old_wait = settings.REMOTE_START_WAIT
    settings.REMOTE_START_WAIT = 17
    _accepting(monkeypatch)
    try:
        response = context["client"].post(
            f"/api/connectors/{context['connector'].id}/remote-start"
        )
        assert response.status_code == 202
        request_row = context["db"].query(RemoteStartRequest).one()
        assert request_row.expires_at == request_row.accepted_at + timedelta(seconds=17)
    finally:
        settings.REMOTE_START_WAIT = old_wait


def test_lazy_expiration_allows_retry_after_wait(context, monkeypatch):
    calls = _accepting(monkeypatch)
    now = [datetime.now(UTC).replace(tzinfo=None)]
    monkeypatch.setattr(remote_start_service, "utc_now_naive", lambda: now[0])
    endpoint = f"/api/connectors/{context['connector'].id}/remote-start"
    first = context["client"].post(endpoint)
    request_id = first.json()["id"]
    now[0] += timedelta(seconds=settings.REMOTE_START_WAIT + 1)
    state = context["client"].get(f"/api/remote-starts/{request_id}")
    assert state.status_code == 200
    assert state.json()["status"] == "expired"
    assert "thử lại" in state.json()["message"]
    second = context["client"].post(endpoint)
    assert second.status_code == 202
    assert second.json()["id"] != request_id
    assert len(calls) == 2


def test_other_driver_cannot_reuse_or_read_an_active_request(context, monkeypatch):
    calls = _accepting(monkeypatch)
    endpoint = f"/api/connectors/{context['connector'].id}/remote-start"
    first = context["client"].post(endpoint)
    app.dependency_overrides[get_current_user] = lambda: context["users"]["driver_b"]
    denied_start = context["client"].post(endpoint)
    denied_read = context["client"].get(f"/api/remote-starts/{first.json()['id']}")
    assert denied_start.status_code == 409
    assert denied_read.status_code == 403
    assert len(calls) == 1


@pytest.mark.parametrize("role", ["station_owner", "operator", "accountant", "admin"])
def test_non_driver_role_is_forbidden(role, context, monkeypatch):
    calls = _accepting(monkeypatch)
    app.dependency_overrides[get_current_user] = lambda: context["users"][role]
    response = context["client"].post(
        f"/api/connectors/{context['connector'].id}/remote-start"
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
    assert calls == []


def test_ensure_virtual_tag_is_idempotent_and_unique(context):
    db = context["db"]
    user_id = context["users"]["driver_a"].id
    first = remote_start_service.ensure_virtual_id_tag(db, user_id)
    second = remote_start_service.ensure_virtual_id_tag(db, user_id)
    db.commit()
    assert first.id == second.id
    assert len(first.id_tag) <= 20
    assert db.query(IdTag).filter_by(user_id=user_id, is_virtual=True).count() == 1
    other = remote_start_service.ensure_virtual_id_tag(
        db, context["users"]["driver_b"].id
    )
    assert other.id_tag != first.id_tag


def test_concurrent_virtual_tag_creation_keeps_one_card(context):
    user_id = context["users"]["driver_a"].id

    def create_tag() -> str:
        db = context["sessions"]()
        try:
            tag = remote_start_service.ensure_virtual_id_tag(db, user_id)
            tag_value = tag.id_tag
            db.commit()
            return tag_value
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        tag_values = list(pool.map(lambda _index: create_tag(), range(2)))
    assert tag_values[0] == tag_values[1]
    assert (
        context["db"]
        .query(IdTag)
        .filter_by(user_id=user_id, is_virtual=True)
        .count()
        == 1
    )


def test_virtual_tag_uses_shared_authorize_decision(context, caplog):
    caplog.set_level(logging.INFO)
    db = context["db"]
    tag = remote_start_service.ensure_virtual_id_tag(
        db, context["users"]["driver_a"].id
    )
    accepted = handle_authorize(db, context["point"], "auth-1", {"idTag": tag.id_tag})
    assert parse_message(accepted)[3]["idTagInfo"]["status"] == "Accepted"
    tag.is_blocked = True
    blocked = handle_authorize(db, context["point"], "auth-2", {"idTag": tag.id_tag})
    assert parse_message(blocked)[3]["idTagInfo"]["status"] == "Blocked"
    assert tag.id_tag not in caplog.text


def test_missing_login_is_unauthorized(context, monkeypatch):
    _accepting(monkeypatch)
    app.dependency_overrides.pop(get_current_user, None)
    response = context["client"].post(
        f"/api/connectors/{context['connector'].id}/remote-start"
    )
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_remote_start_is_blocked_below_wallet_minimum_without_sending_ocpp(
    context, monkeypatch
):
    driver = context["users"]["driver_a"]
    context["db"].add(
        WalletLedgerEntry(
            user_id=driver.id,
            entry_type="session_charge",
            amount_vnd=-25_001,
            idempotency_key="test-start-wallet-below-minimum",
            reference_type="session",
            reference_id=999,
            description="Test balance below minimum",
        )
    )
    context["db"].commit()
    calls = _accepting(monkeypatch)

    response = context["client"].post(
        f"/api/connectors/{context['connector'].id}/remote-start"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Số dư ví cần tối thiểu 25,000 đồng. Hãy nạp thêm tiền để bắt đầu phiên sạc.",
        "code": "wallet_below_minimum",
        "minimum_required_vnd": 25_000,
        "top_up_url": "/wallet",
    }
    assert calls == []
    assert context["db"].query(RemoteStartRequest).count() == 0


def test_remote_start_allows_balance_equal_to_wallet_minimum(context, monkeypatch):
    driver = context["users"]["driver_a"]
    context["db"].add(
        WalletLedgerEntry(
            user_id=driver.id,
            entry_type="session_charge",
            amount_vnd=-25_000,
            idempotency_key="test-start-wallet-exact-minimum",
            reference_type="session",
            reference_id=1001,
            description="Set test balance to minimum",
        )
    )
    context["db"].commit()
    calls = _accepting(monkeypatch)

    response = context["client"].post(
        f"/api/connectors/{context['connector'].id}/remote-start"
    )

    assert response.status_code == 202
    assert calls and calls[0][1] == "RemoteStartTransaction"


def test_authorize_returns_blocked_below_wallet_minimum(context):
    driver = context["users"]["driver_a"]
    context["db"].add(
        WalletLedgerEntry(
            user_id=driver.id,
            entry_type="session_charge",
            amount_vnd=-25_001,
            idempotency_key="test-authorize-wallet-below-minimum",
            reference_type="session",
            reference_id=1000,
            description="Test balance below minimum",
        )
    )
    tag = IdTag(id_tag="DRIVER-TAG-LOW", user_id=driver.id, is_blocked=False)
    context["db"].add(tag)
    context["db"].commit()

    response = handle_authorize(
        context["db"], context["point"], "wallet-low", {"idTag": tag.id_tag}
    )

    assert parse_message(response)[3]["idTagInfo"]["status"] == "Blocked"


def test_invalid_connector_path_has_standard_error_body(context, monkeypatch):
    _accepting(monkeypatch)
    response = context["client"].post("/api/connectors/not-an-int/remote-start")
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_start_with_different_tag_supersedes_waiting_request(context, monkeypatch):
    _accepting(monkeypatch)
    context["client"].post(f"/api/connectors/{context['connector'].id}/remote-start")
    db = context["db"]
    driver_b = context["users"]["driver_b"]
    db.add(IdTag(id_tag="PHYSICAL-TAG", user_id=driver_b.id, is_blocked=False))
    db.commit()
    start = {
        "connectorId": 1,
        "idTag": "PHYSICAL-TAG",
        "meterStart": 100,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    result = handle_start_transaction(db, context["point"], "physical-start", start)
    assert parse_message(result)[0] == 3
    db.commit()
    request_row = db.query(RemoteStartRequest).one()
    assert request_row.status == RemoteStartStatus.SUPERSEDED
    assert request_row.session_id is None


@pytest.mark.parametrize(
    ("age_seconds", "expected_status"),
    [(10, RemoteStartStatus.STARTED), (settings.REMOTE_START_LATE_GRACE + 1, RemoteStartStatus.EXPIRED)],
)
def test_late_start_respects_grace_and_keeps_session(
    age_seconds, expected_status, context
):
    db = context["db"]
    tag = remote_start_service.ensure_virtual_id_tag(db, context["users"]["driver_a"].id)
    now = datetime.now(UTC).replace(tzinfo=None)
    row = RemoteStartRequest(
        driver_user_id=context["users"]["driver_a"].id,
        connector_id=context["connector"].id,
        id_tag_id=tag.id,
        status=RemoteStartStatus.WAITING_START,
        created_at=now - timedelta(seconds=age_seconds),
        accepted_at=now - timedelta(seconds=age_seconds),
        expires_at=now - timedelta(seconds=age_seconds) + timedelta(seconds=settings.REMOTE_START_WAIT),
    )
    db.add(row)
    db.flush()
    session = ChargingSession(
        charge_point_id=context["point"].id,
        charge_point_code=context["point"].code,
        station_id=context["station"].id,
        station_name="Station",
        connector_number=1,
        meter_start_wh=0,
        started_at=now,
        status="active",
    )
    db.add(session)
    db.flush()
    remote_start_service.resolve_pending_start(
        db, context["point"].id, 1, tag.id_tag, session.id, now=now
    )
    db.commit()
    db.refresh(row)
    assert row.status == expected_status
    assert row.session_id == (
        session.id if expected_status == RemoteStartStatus.STARTED else None
    )


def test_start_session_survives_request_resolution_error(context, monkeypatch):
    tag = remote_start_service.ensure_virtual_id_tag(
        context["db"], context["users"]["driver_a"].id
    )

    def fail_resolution(*_args, **_kwargs):
        raise RuntimeError("test resolution fault")

    monkeypatch.setattr(remote_start_service, "resolve_pending_start", fail_resolution)
    payload = {
        "connectorId": 1,
        "idTag": tag.id_tag,
        "meterStart": 400,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    response = handle_start_transaction(context["db"], context["point"], "start-fault", payload)
    assert parse_message(response)[0] == 3
    context["db"].commit()
    assert context["db"].query(ChargingSession).count() == 1


def test_duplicate_active_connector_constraint_is_enforced(context):
    db = context["db"]
    first_tag = remote_start_service.ensure_virtual_id_tag(db, context["users"]["driver_a"].id)
    second_tag = remote_start_service.ensure_virtual_id_tag(db, context["users"]["driver_b"].id)
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add(
        RemoteStartRequest(
            driver_user_id=context["users"]["driver_a"].id,
            connector_id=context["connector"].id,
            id_tag_id=first_tag.id,
            status=RemoteStartStatus.SENDING,
            created_at=now,
        )
    )
    db.commit()
    db.add(
        RemoteStartRequest(
            driver_user_id=context["users"]["driver_b"].id,
            connector_id=context["connector"].id,
            id_tag_id=second_tag.id,
            status=RemoteStartStatus.WAITING_START,
            created_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_two_drivers_racing_for_same_connector_send_one_call(context, monkeypatch):
    calls: list[int] = []

    async def delayed_accept(*_args, **_kwargs):
        calls.append(1)
        await asyncio.sleep(0.02)
        return {"status": "Accepted"}

    monkeypatch.setattr(manager, "send_call", delayed_accept)
    connector_id = context["connector"].id
    user_a = context["users"]["driver_a"].id
    user_b = context["users"]["driver_b"].id

    async def race():
        db_a = context["sessions"]()
        db_b = context["sessions"]()
        try:
            return await asyncio.gather(
                remote_start_service.submit_remote_start(db_a, connector_id, user_a),
                remote_start_service.submit_remote_start(db_b, connector_id, user_b),
                return_exceptions=True,
            )
        finally:
            db_a.close()
            db_b.close()

    results = asyncio.run(race())
    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, remote_start_service.RemoteStartFailure) for result in results) == 1
    assert len(calls) == 1
    assert context["db"].query(RemoteStartRequest).count() == 1


def test_command_wait_does_not_hold_database_write_lock(context, monkeypatch):
    entered = threading.Event()
    release = threading.Event()

    async def waiting_send(*_args, **_kwargs):
        entered.set()
        await asyncio.to_thread(release.wait, 5)
        return {"status": "Accepted"}

    monkeypatch.setattr(manager, "send_call", waiting_send)
    endpoint = f"/api/connectors/{context['connector'].id}/remote-start"
    response_holder = []
    thread = threading.Thread(
        target=lambda: response_holder.append(context["client"].post(endpoint)),
        daemon=True,
    )
    thread.start()
    assert entered.wait(3)

    concurrent_db = context["sessions"]()
    concurrent_db.execute(text("UPDATE stations SET status='active' WHERE id=:id"), {"id": context["station"].id})
    concurrent_db.commit()
    concurrent_db.close()
    release.set()
    thread.join(5)
    assert not thread.is_alive()
    assert response_holder[0].status_code == 202


def test_model_partial_indexes_exist(context):
    indexes = inspect(context["engine"]).get_indexes("remote_start_requests")
    names = {index["name"] for index in indexes}
    assert "uq_remote_start_active_connector" in names
    assert "ix_remote_start_driver_created" in names
    idtag_indexes = inspect(context["engine"]).get_indexes("id_tags")
    assert "uq_virtual_id_tag_per_user" in {index["name"] for index in idtag_indexes}
