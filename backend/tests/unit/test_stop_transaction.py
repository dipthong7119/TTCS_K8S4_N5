"""Test cases cho handler StopTransaction (SCRUM-163 / T-38)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_invoice import ChargingInvoice
from app.models.charging_session import ChargingSession
from app.models.id_tag import IdTag
from app.models.meter_value import MeterValue
from app.models.orphan_message import OrphanMessage
from app.models.station import Station
from app.models.station_tariff import StationTariff, TariffBand
from app.models.user import Role, User
from app.models.wallet_ledger import WalletLedgerEntry
from app.services.ocpp_handlers import handle_ocpp_message
from app.services.ocpp_parser import pack_call, parse_message


@pytest.fixture()
def db_session():
    """Tạo DB in-memory cho test StopTransaction."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    driver_role = Role(id=1, name="driver")
    driver = User(id=1, email="driver@test.com", password_hash="x", full_name="Valid Driver", is_active=True)
    driver.roles = [driver_role]
    db.add(driver)
    
    station = Station(id=1, name="Station 1", owner_id=1, status="active")
    db.add(station)
    
    point = ChargePoint(id=1, code="CP001", station_id=1, status="online")
    db.add(point)
    
    connector = Connector(id=1, charge_point_id=1, connector_id=1, status="charging")
    db.add(connector)
    
    valid_tag = IdTag(id=1, id_tag="VALID-TAG", user_id=1, is_blocked=False)
    db.add(valid_tag)

    # Thêm một ChargingSession đang active để StopTransaction dừng
    session = ChargingSession(
        id=1,
        charge_point_id=1,
        charge_point_code="CP001",
        station_id=1,
        station_name="Station 1",
        connector_number=1,
        user_id=1,
        driver_name="Valid Driver",
        id_tag_id=1,
        id_tag="VALID-TAG",
        meter_start_wh=1000,
        started_at=datetime.now(UTC) - timedelta(hours=1),
        ended_at=None,
        status="active"
    )
    db.add(session)

    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_stop_transaction_valid(db_session):
    """Ca 1: Kết thúc phiên hợp lệ -> cập nhật phiên, trả Accepted."""
    end_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "transactionId": 1,
        "meterStop": 2000,
        "timestamp": end_time,
        "reason": "Local"
    }
    raw_call = pack_call("msg1", "StopTransaction", payload)
    
    raw_response = handle_ocpp_message(db_session, "CP001", raw_call)
    msg_type, msg_id, _, payload_resp, _, _ = parse_message(raw_response)
    
    assert msg_type == 3
    assert msg_id == "msg1"
    assert payload_resp["idTagInfo"]["status"] == "Accepted"
    
    session = db_session.query(ChargingSession).get(1)
    assert session.meter_stop_wh == 2000
    assert session.ended_at is not None
    assert session.stop_reason == "Local"
    assert session.status == "completed"
    
    # Kiểm tra trạng thái connector trở về available
    conn = db_session.query(Connector).filter_by(connector_id=1).first()
    assert conn.status == "available"


def test_stop_transaction_persists_energy_for_sample_sessions(db_session, energy_sample_case):
    case = energy_sample_case
    session = db_session.query(ChargingSession).get(1)
    session.meter_start_wh = case["meter_start_wh"]
    db_session.commit()

    payload = {
        "transactionId": 1,
        "meterStop": case["meter_stop_wh"],
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "reason": "Local",
    }
    raw_response = handle_ocpp_message(
        db_session, "CP001", pack_call("sample-session", "StopTransaction", payload)
    )

    msg_type, _, _, response, _, _ = parse_message(raw_response)
    assert msg_type == 3
    assert response["idTagInfo"]["status"] == "Accepted"

    db_session.refresh(session)
    expected = Decimal(case["expected_kwh"]) if case["expected_kwh"] is not None else None
    assert session.energy_kwh == expected
    assert session.status == case["expected_status"]
    assert session.anomaly_reason == case["expected_anomaly_reason"]


@pytest.mark.parametrize("initial_status", ["active", "anomaly", "needs_review"])
def test_late_stop_closes_original_session_using_device_time(
    db_session, energy_sample_case, initial_status
):
    """T-45/SCRUM-188: Stop muộn đóng cùng transactionId, không đoán thời gian/kWh."""
    case = energy_sample_case
    session = db_session.get(ChargingSession, 1)
    session.meter_start_wh = case["meter_start_wh"]
    session.started_at = datetime(2026, 10, 1, 8, tzinfo=UTC).replace(tzinfo=None)
    session.status = initial_status
    session.anomaly_reason = "offline" if initial_status == "anomaly" else None
    session.review_reason = "connector_available_after_reconnect" if initial_status == "needs_review" else None
    session.remote_stop_requested_at = datetime(2026, 10, 1, 8, 1, tzinfo=UTC).replace(tzinfo=None)
    point = db_session.get(ChargePoint, 1)
    point.status = "offline"
    db_session.commit()

    response = handle_ocpp_message(db_session, point.code, pack_call("late-stop", "StopTransaction", {
        "transactionId": session.id,
        "meterStop": case["meter_stop_wh"],
        "timestamp": "2026-10-01T15:03:00+07:00",
        "reason": "PowerLoss",
    }))

    assert parse_message(response)[0] == 3
    db_session.refresh(session)
    assert session.ended_at == datetime(2026, 10, 1, 8, 3, tzinfo=UTC).replace(tzinfo=None)
    assert session.meter_stop_wh == case["meter_stop_wh"]
    expected = Decimal(case["expected_kwh"]) if case["expected_kwh"] is not None else None
    assert session.energy_kwh == expected
    assert session.status == case["expected_status"]
    assert session.anomaly_reason == case["expected_anomaly_reason"]
    assert session.remote_stop_requested_at is None
    assert session.stop_reason == "PowerLoss"
    assert db_session.query(ChargingSession).count() == 1
    if case["expected_status"] == "completed":
        assert session.review_reason is None


def test_late_stop_filters_buffered_samples_and_replays_without_side_effects(db_session, caplog):
    """T-45: transactionData đi qua cùng quy tắc T-42, không lưu trùng/ghi đè số đo."""
    session = db_session.get(ChargingSession, 1)
    session.started_at = datetime(2026, 10, 1, 8, tzinfo=UTC).replace(tzinfo=None)
    session.status = "anomaly"
    session.anomaly_reason = "offline"
    point = db_session.get(ChargePoint, 1)
    point.status = "offline"
    db_session.add(MeterValue(session_id=1, measured_at=datetime(2026, 10, 1, 8, 1, tzinfo=UTC).replace(tzinfo=None),
                              measurand="Energy.Active.Import.Register", value=1100, unit="Wh"))
    db_session.add(StationTariff(
        station_id=1, name="Flat test tariff", timezone_name="Asia/Ho_Chi_Minh",
        effective_from=session.started_at - timedelta(days=1),
        bands=[TariffBand(label="All day", start_minute=0, end_minute=1440, price_vnd_per_kwh=1000)],
    ))
    db_session.commit()

    def reading(timestamp, value):
        return {"timestamp": timestamp, "sampledValue": [{"value": str(value), "unit": "Wh"}]}

    payload = {"transactionId": 1, "meterStop": 2000, "timestamp": "2026-10-01T08:03:00Z",
               "reason": "PowerLoss", "transactionData": [
                   reading("2026-10-01T08:03:00Z", 2000),
                   reading("2026-10-01T08:01:00Z", 1100),
                   reading("2026-10-01T08:00:30Z", 90000),
                   reading("2026-10-01T08:01:00Z", 1110),
                   reading("2026-10-01T08:02:00Z", 1500),
                   reading("2026-10-01T08:02:00Z", 1500),
               ]}
    raw = pack_call("buffered-stop", "StopTransaction", payload)
    first = handle_ocpp_message(db_session, point.code, raw)
    assert parse_message(first)[0] == 3
    rows = db_session.query(MeterValue).order_by(MeterValue.measured_at).all()
    assert [(row.measured_at, row.value) for row in rows] == [
        (datetime(2026, 10, 1, 8, 1, tzinfo=UTC).replace(tzinfo=None), Decimal(1100)),
        (datetime(2026, 10, 1, 8, 2, tzinfo=UTC).replace(tzinfo=None), Decimal(1500)),
        (datetime(2026, 10, 1, 8, 3, tzinfo=UTC).replace(tzinfo=None), Decimal(2000)),
    ]
    warnings = [record for record in caplog.records if "Meter value rejected" in record.message]
    assert len(warnings) == 2
    assert handle_ocpp_message(db_session, point.code, raw) == first
    second = handle_ocpp_message(db_session, point.code, pack_call("stop-again", "StopTransaction", {
        **payload, "meterStop": 99999, "timestamp": "2026-10-02T08:00:00Z",
    }))
    assert parse_message(second)[0] == 3
    db_session.refresh(session)
    assert session.energy_kwh == Decimal("1.000")
    assert session.meter_stop_wh == 2000
    assert session.ended_at == datetime(2026, 10, 1, 8, 3, tzinfo=UTC).replace(tzinfo=None)
    assert db_session.query(MeterValue).count() == 3
    # Manual billing oracle: 1.000 kWh * 1000 VND/kWh = 1000 VND, charged once.
    assert db_session.query(ChargingInvoice).one().total_vnd == 1000
    assert db_session.query(WalletLedgerEntry).one().amount_vnd == -1000


def test_late_stop_billing_keeps_saved_readings_when_backlog_duplicates_them(db_session):
    """T-45: lọc bản gửi lại không làm mất mốc tính tiền đã lưu trước đó."""
    session = db_session.get(ChargingSession, 1)
    session.started_at = datetime(2026, 10, 1, 8, tzinfo=UTC).replace(tzinfo=None)
    session.status = "anomaly"
    session.anomaly_reason = "offline"
    point = db_session.get(ChargePoint, 1)
    point.status = "offline"
    db_session.add(MeterValue(
        session_id=1, measured_at=session.started_at + timedelta(minutes=1),
        measurand="Energy.Active.Import.Register", value=1200, unit="Wh",
    ))
    db_session.add(StationTariff(
        station_id=1, name="Two time bands", timezone_name="UTC",
        effective_from=session.started_at - timedelta(days=1), bands=[
            TariffBand(label="Before 08:01", start_minute=0, end_minute=481, price_vnd_per_kwh=1000),
            TariffBand(label="After 08:01", start_minute=481, end_minute=1440, price_vnd_per_kwh=2000),
        ],
    ))
    db_session.commit()
    response = handle_ocpp_message(db_session, point.code, pack_call("stop-billing-backlog", "StopTransaction", {
        "transactionId": 1, "meterStop": 2000, "timestamp": "2026-10-01T08:02:00Z",
        "transactionData": [
            {"timestamp": "2026-10-01T08:01:00Z", "sampledValue": [{"value": "1200", "unit": "Wh"}]},
            {"timestamp": "2026-10-01T08:02:00Z", "sampledValue": [{"value": "2000", "unit": "Wh"}]},
        ],
    }))
    assert parse_message(response)[0] == 3
    # Manual oracle: 0.200 kWh * 1000 + 0.800 kWh * 2000 = 1800 VND.
    assert db_session.query(ChargingInvoice).one().total_vnd == 1800
    assert db_session.query(WalletLedgerEntry).one().amount_vnd == -1800
    assert db_session.query(MeterValue).count() == 2


def test_stop_transaction_invalid_transaction_id(db_session):
    """Ca 2: transactionId không tồn tại -> lưu vào orphan_messages, trả về {}."""
    end_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "transactionId": 999,
        "meterStop": 2000,
        "timestamp": end_time,
        "reason": "Local",
        "transactionData": []
    }
    raw_call = pack_call("msg2", "StopTransaction", payload)
    
    raw_response = handle_ocpp_message(db_session, "CP001", raw_call)
    msg_type, msg_id, _, payload_resp, _, _ = parse_message(raw_response)
    
    assert msg_type == 3
    assert msg_id == "msg2"
    assert payload_resp == {}  # Empty result as defined in _dispatch fallback
    
    orphan = db_session.query(OrphanMessage).filter_by(transaction_id=999).first()
    assert orphan is not None
    assert orphan.action == "StopTransaction"
    assert orphan.reason == "transaction_not_found"


def test_stop_transaction_idempotency(db_session):
    """Ca 3: Trụ gửi lại StopTransaction cùng mã tin nhắn -> idempotent, trả Accepted."""
    end_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "transactionId": 1,
        "meterStop": 2000,
        "timestamp": end_time,
        "reason": "Local"
    }
    raw_call = pack_call("msg_dup", "StopTransaction", payload)
    
    # Gửi lần 1
    raw_resp1 = handle_ocpp_message(db_session, "CP001", raw_call)
    
    # Gửi lần 2
    raw_resp2 = handle_ocpp_message(db_session, "CP001", raw_call)
    
    assert raw_resp1 == raw_resp2
    session = db_session.query(ChargingSession).get(1)
    assert session.meter_stop_wh == 2000


def test_stop_transaction_already_ended(db_session):
    """Ca 4: Trụ gửi StopTransaction cho phiên đã đóng (transactionId đúng nhưng tin nhắn mới) -> trả Accepted, không lỗi."""
    # Đóng phiên trước
    session = db_session.query(ChargingSession).get(1)
    session.ended_at = datetime.now(UTC)
    session.meter_stop_wh = 1500
    db_session.commit()
    
    end_time = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "transactionId": 1,
        "meterStop": 2000,
        "timestamp": end_time,
        "reason": "Local"
    }
    raw_call = pack_call("msg3", "StopTransaction", payload)
    
    raw_response = handle_ocpp_message(db_session, "CP001", raw_call)
    _, _, _, payload_resp, _, _ = parse_message(raw_response)
    
    assert payload_resp["idTagInfo"]["status"] == "Accepted"
    
    # Không đổi meter_stop_wh
    session = db_session.query(ChargingSession).get(1)
    assert session.meter_stop_wh == 1500


def test_stop_transaction_validation_errors(db_session):
    """Bắt lỗi dữ liệu không hợp lệ (FormationViolation)."""
    # transactionId âm
    payload = {"transactionId": -1, "meterStop": 2000, "timestamp": datetime.now(UTC).isoformat()}
    resp = handle_ocpp_message(db_session, "CP001", pack_call("m1", "StopTransaction", payload))
    assert parse_message(resp)[3] == "FormationViolation"
    
    # meterStop âm
    payload = {"transactionId": 1, "meterStop": -5, "timestamp": datetime.now(UTC).isoformat()}
    resp = handle_ocpp_message(db_session, "CP001", pack_call("m2", "StopTransaction", payload))
    assert parse_message(resp)[3] == "FormationViolation"
    
    # Thiếu timestamp
    payload = {"transactionId": 1, "meterStop": 2000}
    resp = handle_ocpp_message(db_session, "CP001", pack_call("m3", "StopTransaction", payload))
    assert parse_message(resp)[3] == "FormationViolation"
    
    # transactionData không phải array
    payload = {"transactionId": 1, "meterStop": 2000, "timestamp": datetime.now(UTC).isoformat(), "transactionData": {}}
    resp = handle_ocpp_message(db_session, "CP001", pack_call("m4", "StopTransaction", payload))
    assert parse_message(resp)[3] == "FormationViolation"
