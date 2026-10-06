import pytest
import datetime
from decimal import Decimal
from app.models.meter_value import MeterValue
from app.models.orphan_message import OrphanMessage
from app.models.charging_session import ChargingSession
from app.ocpp.handlers.meter_values import handle_meter_values, parse_meter_values
import json

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
    with pytest.raises(ValueError, match="meterValue must be an array"):
        parse_meter_values({"connectorId": 1, "meterValue": {}})
        
    with pytest.raises(ValueError, match="Missing timestamp"):
        parse_meter_values({"connectorId": 1, "meterValue": [{"sampledValue": []}]})

# Tích hợp Database test
def test_handle_meter_values_ac1_ac2(db, dummy_charge_point):
    """AC1 & AC2: Ghi dữ liệu vào phiên đang sạc, lọc đúng đại lượng."""
    session = ChargingSession(
        charge_point_id=dummy_charge_point.id,
        charge_point_code=dummy_charge_point.code,
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
    result_dict = json.loads(response[3]) if isinstance(response, list) else json.loads(response.split(',', 3)[-1][:-1]) # parse conf
    
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
                "timestamp": "2023-01-01T10:00:00Z",
                "sampledValue": [{"value": "123", "measurand": "Power.Active.Import"}]
            }
        ]
    }
    
    start_time = time.time()
    for i in range(20):
        handle_meter_values(db, dummy_charge_point, f"msg-perf-{i}", payload)
    
    duration = time.time() - start_time
    # Trung bình mỗi request phải < 200ms -> 20 request phải < 4s
    assert duration < 4.0
    
    count = db.query(MeterValue).filter_by(session_id=session.id).count()
    assert count == 20
