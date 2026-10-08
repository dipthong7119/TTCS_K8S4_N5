"""Kiểm thử đối chiếu phiên sạc khi trụ kết nối trở lại."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.meter_value import MeterValue
from app.models.station import Station
from app.models.user import User
from app.ocpp.handlers.status_notification import handle_status_notification
from app.ocpp.session_reconciliation import (
    OPEN_SESSION_STATUSES,
    ReconciliationContext,
    ReconciliationDecision,
    _open_sessions_statement,
    begin_reconciliation,
    decide_reconciliation,
)
from app.routers import ocpp as ocpp_router
from app.services.connection_manager import ConnectionManager
from app.services.jobs import expire_stale_charge_points_once
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, parse_message


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = session_factory()
    user = User(email="reconcile@example.test", password_hash="test", full_name="Test")
    db.add(user)
    db.flush()
    station = Station(name="Reconcile station", owner_id=user.id, status="active")
    db.add(station)
    db.flush()
    point = ChargePoint(
        code="CP-RECONNECT",
        station_id=station.id,
        status="online",
        last_seen_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(point)
    db.flush()
    db.add_all(
        Connector(
            charge_point_id=point.id,
            connector_id=connector_id,
            status="unknown",
        )
        for connector_id in (1, 2, 3)
    )
    db.commit()
    try:
        yield db, point
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _add_session(
    db_session,
    point: ChargePoint,
    connector_id: int,
    *,
    status: str = "active",
    ended_at: datetime | None = None,
) -> ChargingSession:
    db, _ = db_session
    session = ChargingSession(
        charge_point_id=point.id,
        charge_point_code=point.code,
        station_id=point.station_id,
        station_name="Reconcile station",
        connector_number=connector_id,
        meter_start_wh=1000,
        started_at=datetime(2026, 10, 7, 10, 0),
        ended_at=ended_at,
        status=status,
    )
    db.add(session)
    db.commit()
    return session


def _send_status(
    db,
    point: ChargePoint,
    context: ReconciliationContext,
    connector_id: int,
    status: str,
    message_id: str,
) -> dict:
    response = handle_ocpp_message(
        db,
        point.code,
        pack_call(
            message_id,
            "StatusNotification",
            {"connectorId": connector_id, "status": status, "errorCode": "NoError"},
        ),
        context,
    )
    frame = parse_message(response)
    assert frame[0] == 3
    return frame[3]


def _raise_reconciliation_error(*_args) -> None:
    raise RuntimeError("simulated")


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("Charging", ReconciliationDecision.KEEP),
        ("SuspendedEV", ReconciliationDecision.KEEP),
        ("SuspendedEVSE", ReconciliationDecision.KEEP),
        ("Available", ReconciliationDecision.FLAG),
        ("Preparing", ReconciliationDecision.NONE),
        ("Finishing", ReconciliationDecision.NONE),
        ("Reserved", ReconciliationDecision.NONE),
        ("Unavailable", ReconciliationDecision.NONE),
        ("Faulted", ReconciliationDecision.NONE),
        ("Foo", ReconciliationDecision.NONE),
        ("", ReconciliationDecision.NONE),
    ],
)
def test_decide_reconciliation_table(status, expected):
    assert decide_reconciliation(status) is expected


def test_begin_reconciliation_rebuilds_open_sessions_without_writes(db_session):
    db, point = db_session
    active = _add_session(db_session, point, 1)
    needs_review = _add_session(db_session, point, 2, status="needs_review")
    anomaly = _add_session(db_session, point, 3, status="anomaly")
    _add_session(
        db_session,
        point,
        3,
        status="completed",
        ended_at=datetime(2026, 10, 7, 11, 0),
    )
    context = ReconciliationContext()
    statements: list[str] = []

    def count_statement(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", count_statement)
    try:
        first = begin_reconciliation(db, point, context)
        second = begin_reconciliation(db, point, context)
    finally:
        event.remove(db.bind, "before_cursor_execute", count_statement)

    assert first == second == {1: active.id, 2: needs_review.id, 3: anomaly.id}
    assert len(statements) == 2
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
    assert [active.status, needs_review.status, anomaly.status] == [
        "active", "needs_review", "anomaly"
    ]
    assert OPEN_SESSION_STATUSES == ("active", "needs_review", "anomaly")


def test_reconciliation_query_uses_session_connector_index(db_session):
    db, point = db_session
    statement = _open_sessions_statement(point.id)
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    plan = db.execute(text(f"EXPLAIN QUERY PLAN {sql}")).all()
    plan_text = " ".join(str(row) for row in plan).lower()
    assert "uq_active_session_per_connector" in plan_text
    assert "charging_sessions" in sql
    assert "connectors" in sql


def test_charging_keeps_existing_session_without_session_update(db_session):
    db, point = db_session
    session = _add_session(db_session, point, 1)
    context = ReconciliationContext()
    begin_reconciliation(db, point, context)
    updates: list[str] = []

    def record_update(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("UPDATE CHARGING_SESSIONS"):
            updates.append(statement)

    event.listen(db.bind, "before_cursor_execute", record_update)
    try:
        assert _send_status(db, point, context, 1, "Charging", "charging-1") == {}
        _send_status(db, point, context, 1, "Available", "available-after-keep")
    finally:
        event.remove(db.bind, "before_cursor_execute", record_update)

    db.refresh(session)
    assert updates == []
    assert context.decided == {1}
    assert session.status == "active"
    assert session.ended_at is None
    assert db.query(ChargingSession).filter_by(charge_point_id=point.id).count() == 1
    assert context.waiting == {}


def test_available_flags_once_without_closing_session(db_session, caplog):
    db, point = db_session
    session = _add_session(db_session, point, 1)
    context = ReconciliationContext()
    begin_reconciliation(db, point, context)

    _send_status(db, point, context, 1, "Available", "available-1")
    _send_status(db, point, context, 1, "Available", "available-2")
    db.refresh(session)

    warnings = [record for record in caplog.records if record.levelname == "WARNING"]
    assert session.status == "needs_review"
    assert session.review_reason == "connector_available_after_reconnect"
    assert session.ended_at is None
    assert session.energy_kwh is None
    assert len(warnings) == 1
    assert "cp=CP-RECONNECT connector=1 transaction=" in warnings[0].message
    assert "decision=FLAG" in warnings[0].message
    assert context.waiting == {}


@pytest.mark.parametrize("status", ["needs_review", "anomaly"])
def test_available_does_not_overwrite_other_open_statuses(db_session, status):
    db, point = db_session
    session = _add_session(db_session, point, 1, status=status)
    session.review_reason = "existing_reason"
    db.commit()
    context = ReconciliationContext()
    begin_reconciliation(db, point, context)

    _send_status(db, point, context, 1, "Available", f"available-{status}")
    db.refresh(session)

    assert session.status == status
    assert session.review_reason == "existing_reason"
    assert session.ended_at is None
    assert context.waiting == {}


def test_none_keeps_pending_and_unknown_connector_does_not_touch_it(db_session):
    db, point = db_session
    session = _add_session(db_session, point, 1)
    context = ReconciliationContext()
    begin_reconciliation(db, point, context)

    _send_status(db, point, context, 1, "Preparing", "preparing")
    assert context.waiting == {1: session.id}
    assert handle_status_notification(
        db, point.code, "zero", {"connectorId": 0, "status": "Available"}, context
    ).startswith("[3")
    assert handle_status_notification(
        db, point.code, "unknown", {"connectorId": 99, "status": "Available"}, context
    ).startswith("[3")
    assert context.waiting == {1: session.id}


def test_multiple_connectors_and_charging_without_open_session(db_session, caplog):
    db, point = db_session
    session1 = _add_session(db_session, point, 1)
    session2 = _add_session(db_session, point, 2)
    context = ReconciliationContext()
    begin_reconciliation(db, point, context)

    _send_status(db, point, context, 1, "Charging", "multi-1")
    _send_status(db, point, context, 2, "Available", "multi-2")
    _send_status(db, point, context, 3, "Charging", "multi-3")
    db.refresh(session1)
    db.refresh(session2)

    assert session1.status == "active"
    assert session2.status == "needs_review"
    assert context.waiting == {}
    assert any(
        record.levelname == "INFO" and "connector=3" in record.message
        for record in caplog.records
    )
    assert db.query(ChargingSession).count() == 2


def test_new_connection_rebuilds_map_from_database(db_session):
    db, point = db_session
    session = _add_session(db_session, point, 1)
    old_context = ReconciliationContext()
    begin_reconciliation(db, point, old_context)
    new_context = ReconciliationContext()
    assert begin_reconciliation(db, point, new_context) == {1: session.id}
    assert new_context.waiting == {1: session.id}
    assert old_context.waiting is not new_context.waiting


def test_offline_message_rebuilds_and_late_meter_stop_use_same_transaction(db_session, monkeypatch):
    db, point = db_session
    session = _add_session(db_session, point, 1)
    point.status = "offline"
    db.commit()
    context = ReconciliationContext()

    response = handle_ocpp_message(db, point.code, pack_call("heartbeat", "Heartbeat", {}), context)
    assert parse_message(response)[0] == 3
    assert context.waiting == {1: session.id}
    db.refresh(session)
    assert session.status == "active"
    assert session.ended_at is None

    _send_status(db, point, context, 1, "Charging", "returning-status")
    meter_response = handle_ocpp_message(
        db,
        point.code,
        pack_call("meter", "MeterValues", {
            "connectorId": 1,
            "transactionId": session.id,
            "meterValue": [{
                "timestamp": "2026-10-07T10:01:00Z",
                "sampledValue": [{"value": "1100", "unit": "Wh"}],
            }],
        }),
        context,
    )
    assert parse_message(meter_response)[0] == 3
    monkeypatch.setattr(
        "app.ocpp.handlers.stop_transaction.finalize_session_billing",
        lambda *_args: None,
    )
    stop_response = handle_ocpp_message(
        db,
        point.code,
        pack_call("stop", "StopTransaction", {
            "transactionId": session.id,
            "meterStop": 1200,
            "timestamp": "2026-10-07T10:02:00Z",
            "reason": "EVDisconnected",
        }),
        context,
    )
    assert parse_message(stop_response)[0] == 3
    db.refresh(session)
    assert db.query(MeterValue).filter_by(session_id=session.id).count() == 1
    assert session.status == "completed"
    assert session.ended_at is not None


def test_reconciliation_failure_keeps_connector_response_and_context(db_session, monkeypatch):
    db, point = db_session
    session = _add_session(db_session, point, 1)
    context = ReconciliationContext(waiting={1: session.id})
    monkeypatch.setattr(
        "app.ocpp.handlers.status_notification.reconcile_status_notification",
        _raise_reconciliation_error,
    )

    response = handle_status_notification(
        db,
        point.code,
        "fault-injection",
        {"connectorId": 1, "status": "Charging", "errorCode": "NoError"},
        context,
    )

    assert parse_message(response)[0:4:3] == (3, {})
    connector = db.query(Connector).filter_by(charge_point_id=point.id, connector_id=1).one()
    assert connector.ocpp_status == "Charging"
    assert connector.status == "busy"
    assert context.waiting == {1: session.id}


def test_offline_charge_point_job_and_websocket_close_leave_session_open(
    db_session, monkeypatch
):
    db, point = db_session
    session = _add_session(db_session, point, 1)
    point.last_seen_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2)
    db.commit()
    monkeypatch.setattr("app.routers.monitoring.notify_status_change", lambda *_args: None)

    assert expire_stale_charge_points_once(db) == 1
    db.refresh(session)
    assert session.status == "active"
    assert session.ended_at is None
    session_id = session.id
    db.close()

    manager = ConnectionManager()
    monkeypatch.setattr(ocpp_router, "manager", manager)
    monkeypatch.setattr(ocpp_router, "SessionLocal", sessionmaker(bind=db.bind))
    monkeypatch.setattr(
        "app.services.ocpp_handlers.publish_charge_point_status", lambda *_args: None
    )

    class FakeWebSocket:
        headers = {"sec-websocket-protocol": "ocpp1.6"}
        client = type("Client", (), {"host": "127.0.0.1"})()

        def __init__(self):
            self.frames = [pack_call("boot-close", "BootNotification", {
                "chargePointVendor": "Test",
                "chargePointModel": "TestModel",
            })]

        async def accept(self, *, subprotocol):
            assert subprotocol == "ocpp1.6"

        async def receive_text(self):
            if self.frames:
                return self.frames.pop(0)
            from fastapi import WebSocketDisconnect

            raise WebSocketDisconnect(code=1000)

        async def send_text(self, _message):
            return None

        async def close(self, **_kwargs):
            return None

    asyncio.run(ocpp_router.ocpp_websocket_endpoint(FakeWebSocket(), point.code))
    verify_db = sessionmaker(bind=db.bind)()
    persisted_session = verify_db.get(ChargingSession, session_id)
    assert persisted_session is not None
    assert persisted_session.status == "active"
    assert persisted_session.ended_at is None
    verify_db.close()
