import datetime
import json
from decimal import Decimal

import pytest

from app.models.charging_session import ChargingSession
from app.models.meter_value import MeterValue
from app.models.orphan_message import OrphanMessage
from app.ocpp.handlers.meter_values import (
    Decision,
    decide_sample,
    handle_meter_values,
    parse_meter_values,
)


@pytest.fixture
def dummy_charge_point(db):
    from app.models.charge_point import ChargePoint
    from app.models.station import Station
    from app.models.user import User

    owner = User(email="meter-owner@example.com", password_hash="test", full_name="Meter owner")
    db.add(owner)
    db.flush()
    station = Station(name="Meter test station", owner_id=owner.id, status="active")
    db.add(station)
    db.flush()
    point = ChargePoint(code="METER-TEST", station_id=station.id, status="online")
    db.add(point)
    db.commit()
    return point

def test_parse_meter_values_basic():
    """Hàm phân tích thuần: đúng định dạng, lọc đại lượng lạ."""
    payload = {
        "connectorId": 1,
        "meterValue": [
            {
                "timestamp": "2023-01-01T10:00:00Z",
                "sampledValue": [
                    {"value": "123.45", "measurand": "Energy.Active.Import.Register", "unit": "Wh"},
                    {"value": "230", "measurand": "Voltage", "unit": "V"},  # Bị bỏ qua
                    {"value": "32.1", "measurand": "Current.Import", "unit": "A"},
                ]
            }
        ]
    }
    result = parse_meter_values(payload)
    assert len(result) == 2
    assert result[0]["measurand"] == "Energy.Active.Import.Register"
    assert result[0]["value"] == Decimal("123.45")
    assert result[0]["unit"] == "Wh"
    assert result[1]["measurand"] == "Current.Import"

def test_parse_meter_values_missing_measurand():
    """Thiếu measurand -> mặc định Energy.Active.Import.Register."""
    payload = {
        "connectorId": 1,
        "meterValue": [
            {
                "timestamp": "2023-01-01T10:00:00Z",
                "sampledValue": [
                    {"value": "100", "unit": "kWh"}
                ]
            }
        ]
    }
    result = parse_meter_values(payload)
    assert len(result) == 1
    assert result[0]["measurand"] == "Energy.Active.Import.Register"
    assert result[0]["unit"] == "kWh"

def test_parse_meter_values_invalid_value(caplog):
    """Giá trị value không phải số -> dòng đó bị bỏ qua, không chết toàn bộ payload."""
    payload = {
        "connectorId": 1,
        "meterValue": [
            {
                "timestamp": "2023-01-01T10:00:00Z",
                "sampledValue": [
                    {"value": "100.5", "measurand": "Power.Active.Import"},
                    {"value": "abc", "measurand": "Current.Import"}
                ]
            }
        ]
    }
    result = parse_meter_values(payload)
    assert len(result) == 1
    assert result[0]["measurand"] == "Power.Active.Import"
    assert "Invalid number format for value: abc" in caplog.text

def test_parse_meter_values_formation_errors():
    """Cấu trúc sai trả về ValueError."""
    with pytest.raises(TypeError, match="meterValue must be an array"):
        parse_meter_values({"connectorId": 1, "meterValue": {}})

    with pytest.raises(ValueError, match="Missing timestamp"):
        parse_meter_values({"connectorId": 1, "meterValue": [{"sampledValue": []}]})

# Tích hợp Database test
def test_handle_meter_values_ac1_ac2(db, dummy_charge_point):
    """AC1 & AC2: Ghi dữ liệu vào phiên đang sạc, lọc đúng đại lượng."""
    session = ChargingSession(
        charge_point_id=dummy_charge_point.id,
        charge_point_code=dummy_charge_point.code,
        station_name="Meter test station",
        connector_number=1,
        meter_start_wh=0,
        started_at=datetime.datetime.now(datetime.timezone.utc),
        status="active"
    )
    db.add(session)
    db.commit()

    payload = {
        "connectorId": 1,
        "transactionId": session.id,
        "meterValue": [
            {
                "timestamp": "2023-01-01T10:00:00Z",
                "sampledValue": [
                    {"value": "123", "measurand": "Energy.Active.Import.Register", "unit": "Wh"},
                    {"value": "10", "measurand": "Power.Active.Import"},
                    {"value": "220", "measurand": "Voltage"} # Bỏ qua
                ]
            }
        ]
    }

    response = handle_meter_values(db, dummy_charge_point, "msg-123", payload)
    # The OCPP dispatcher commits handler writes; this direct unit call must
    # exercise the same transaction boundary with autoflush disabled.
    db.commit()
    assert json.loads(response) == [3, "msg-123", {}]

    # Check return conf
    assert 'msg-123' in response
    assert response.startswith('[3')

    records = db.query(MeterValue).filter_by(session_id=session.id).all()
    assert len(records) == 2
    measurands = [r.measurand for r in records]
    assert "Energy.Active.Import.Register" in measurands
    assert "Power.Active.Import" in measurands
    assert "Voltage" not in measurands

def test_handle_meter_values_ac3_orphan(db, dummy_charge_point):
    """AC3: Đầu nối không có phiên chạy -> vào bảng orphan_messages."""
    payload = {
        "connectorId": 1,
        "meterValue": [
            {
                "timestamp": "2023-01-01T10:00:00Z",
                "sampledValue": [{"value": "123", "measurand": "Power.Active.Import"}]
            }
        ]
    }

    response = handle_meter_values(db, dummy_charge_point, "msg-orphan", payload)
    db.commit()
    assert response.startswith('[3')

    records = db.query(MeterValue).all()
    assert len(records) == 0

    orphans = db.query(OrphanMessage).filter_by(charge_point_code=dummy_charge_point.code).all()
    assert len(orphans) == 1
    assert orphans[0].reason == "no_active_session"
    assert orphans[0].action == "MeterValues"

@pytest.mark.asyncio
async def test_handle_meter_values_ac4_perf(db, dummy_charge_point):
    """AC4: Tải nhẹ, phản hồi nhanh (không dùng sleep, chỉ loop xử lý liên tục)."""
    import time

    session = ChargingSession(
        charge_point_id=dummy_charge_point.id,
        charge_point_code=dummy_charge_point.code,
        station_name="Meter test station",
        connector_number=1,
        meter_start_wh=0,
        started_at=datetime.datetime.now(datetime.timezone.utc),
        status="active"
    )
    db.add(session)
    db.commit()

    payload = {
        "connectorId": 1,
        "meterValue": [
            {
                "timestamp": f"2023-01-01T10:00:{i:02d}Z",
                "sampledValue": [{"value": "123", "measurand": "Power.Active.Import"}]
            }
        ]
    }

    start_time = time.time()
    for i in range(20):
        handle_meter_values(db, dummy_charge_point, f"msg-perf-{i}", payload)
        db.commit()

    duration = time.time() - start_time
    # Trung bình mỗi request phải < 200ms -> 20 request phải < 4s
    assert duration < 4.0

    count = db.query(MeterValue).filter_by(session_id=session.id).count()
    assert count == 20


@pytest.mark.parametrize(
    ("offset_seconds", "new_value", "measurand", "old_value", "old_unit", "new_unit", "expected"),
    [
        (-1, "999", "Energy.Active.Import.Register", "10", "Wh", "Wh", Decision.SKIP_WARN),
        (0, "10", "Energy.Active.Import.Register", "10", "Wh", "Wh", Decision.SKIP_SILENT),
        (0, "11", "Energy.Active.Import.Register", "10", "Wh", "Wh", Decision.SKIP_WARN),
        (1, "11", "Energy.Active.Import.Register", "10", "Wh", "Wh", Decision.STORE),
        (1, "10", "Energy.Active.Import.Register", "10", "Wh", "Wh", Decision.STORE),
        (1, "9", "Energy.Active.Import.Register", "10", "Wh", "Wh", Decision.STORE_AND_FLAG),
        (1, "9", "Power.Active.Import", "10", "W", "W", Decision.STORE),
        (1, "9", "Current.Import", "10", "A", "A", Decision.STORE),
        (0, "12.345", "Energy.Active.Import.Register", "12345", "Wh", "kWh", Decision.SKIP_SILENT),
        (1, "12", "Energy.Active.Import.Register", "12345", "Wh", "kWh", Decision.STORE_AND_FLAG),
    ],
)
def test_decide_sample_table(
    offset_seconds, new_value, measurand, old_value, old_unit, new_unit, expected
):
    base = datetime.datetime(2026, 10, 7, tzinfo=datetime.timezone.utc)
    old = {
        "measured_at": base,
        "measurand": measurand,
        "value": Decimal(old_value),
        "unit": old_unit,
    }
    new = {
        "measured_at": base + datetime.timedelta(seconds=offset_seconds),
        "measurand": measurand,
        "value": Decimal(new_value),
        "unit": new_unit,
    }
    assert decide_sample(new, old) is expected


def test_decide_sample_without_latest():
    sample = {
        "measured_at": datetime.datetime.now(datetime.timezone.utc),
        "measurand": "Energy.Active.Import.Register",
        "value": Decimal("1"),
        "unit": None,
    }
    assert decide_sample(sample, None) is Decision.STORE


def test_meter_value_old_sample_warns_and_duplicate_is_silent(db, dummy_charge_point, caplog):
    session = ChargingSession(
        charge_point_id=dummy_charge_point.id,
        charge_point_code=dummy_charge_point.code,
        station_name="Meter test station",
        connector_number=1,
        meter_start_wh=0,
        started_at=datetime.datetime.now(datetime.timezone.utc),
        status="active",
    )
    db.add(session)
    db.commit()
    payload = {
        "connectorId": 1,
        "transactionId": session.id,
        "meterValue": [{
            "timestamp": "2026-10-07T10:00:00Z",
            "sampledValue": [{
                "value": "100", "measurand": "Energy.Active.Import.Register", "unit": "Wh"
            }],
        }],
    }
    handle_meter_values(db, dummy_charge_point, "new", payload)
    db.commit()
    older = {**payload, "meterValue": [{**payload["meterValue"][0], "timestamp": "2026-10-07T09:59:00Z"}]}
    handle_meter_values(db, dummy_charge_point, "old", older)
    db.commit()
    assert "old_at=2026-10-07T10:00:00" in caplog.text
    warning_count = sum(record.levelname == "WARNING" for record in caplog.records)
    handle_meter_values(db, dummy_charge_point, "duplicate", payload)
    db.commit()
    assert sum(record.levelname == "WARNING" for record in caplog.records) == warning_count
    assert db.query(MeterValue).filter_by(session_id=session.id).count() == 1


def test_lower_energy_value_is_stored_and_flags_session(db, dummy_charge_point):
    session = ChargingSession(
        charge_point_id=dummy_charge_point.id,
        charge_point_code=dummy_charge_point.code,
        station_name="Meter test station",
        connector_number=1,
        meter_start_wh=0,
        started_at=datetime.datetime.now(datetime.timezone.utc),
        status="active",
    )
    db.add(session)
    db.commit()
    for timestamp, value in [("2026-10-07T10:00:00Z", "100"), ("2026-10-07T10:01:00Z", "90")]:
        handle_meter_values(db, dummy_charge_point, timestamp, {
            "connectorId": 1,
            "transactionId": session.id,
            "meterValue": [{
                "timestamp": timestamp,
                "sampledValue": [{"value": value, "measurand": "Energy.Active.Import.Register"}],
            }],
        })
        db.commit()
    db.refresh(session)
    assert session.needs_review is True
    assert session.review_reason == "meter_value_decreased"
    assert db.query(MeterValue).filter_by(session_id=session.id).count() == 2


def test_unsorted_values_skip_sample_older_than_saved_latest(db, dummy_charge_point):
    session = ChargingSession(
        charge_point_id=dummy_charge_point.id,
        charge_point_code=dummy_charge_point.code,
        station_name="Meter test station",
        connector_number=1,
        meter_start_wh=0,
        started_at=datetime.datetime.now(datetime.timezone.utc),
        status="active",
    )
    db.add(session)
    db.commit()
    db.add(MeterValue(
        session_id=session.id,
        measured_at=datetime.datetime(2026, 10, 7, 10, 1),
        measurand="Energy.Active.Import.Register",
        value=90,
        unit="Wh",
    ))
    db.commit()
    response = handle_meter_values(db, dummy_charge_point, "batch", {
        "connectorId": 1,
        "transactionId": session.id,
        "meterValue": [
            {"timestamp": "2026-10-07T10:02:00Z", "sampledValue": [{"value": "80"}]},
            {"timestamp": "2026-10-07T10:00:00Z", "sampledValue": [{"value": "100"}]},
        ],
    })
    db.commit()
    records = db.query(MeterValue).filter_by(session_id=session.id).order_by(MeterValue.measured_at).all()
    assert response.startswith("[3")
    assert [record.value for record in records] == [Decimal("90"), Decimal("80")]
    assert session.needs_review is True
