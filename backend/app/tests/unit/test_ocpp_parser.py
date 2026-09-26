import pytest
import json
from app.services.ocpp_parser import parse_message, pack_call, pack_call_result, pack_call_error

def test_parse_valid_call():
    raw = json.dumps([2, "12345", "BootNotification", {"chargePointVendor": "Vendor"}])
    msg_type, msg_id, action, payload, _, _ = parse_message(raw)
    assert msg_type == 2
    assert msg_id == "12345"
    assert action == "BootNotification"
    assert payload == {"chargePointVendor": "Vendor"}

def test_parse_valid_callresult():
    raw = json.dumps([3, "12345", {"status": "Accepted"}])
    msg_type, msg_id, _, payload, _, _ = parse_message(raw)
    assert msg_type == 3
    assert msg_id == "12345"
    assert payload == {"status": "Accepted"}

def test_parse_valid_callerror():
    raw = json.dumps([4, "12345", "NotSupported", "Action is not supported", {}])
    msg_type, msg_id, _, err_code, err_desc, err_details = parse_message(raw)
    assert msg_type == 4
    assert msg_id == "12345"
    assert err_code == "NotSupported"
    assert err_desc == "Action is not supported"
    assert err_details == {}

def test_pack_call():
    raw = pack_call("123", "BootNotification", {"vendor": "X"})
    assert json.loads(raw) == [2, "123", "BootNotification", {"vendor": "X"}]

def test_pack_call_result():
    raw = pack_call_result("123", {"status": "Accepted"})
    assert json.loads(raw) == [3, "123", {"status": "Accepted"}]

def test_pack_call_error():
    raw = pack_call_error("123", "NotSupported", "Desc", {"detail": 1})
    assert json.loads(raw) == [4, "123", "NotSupported", "Desc", {"detail": 1}]

@pytest.mark.parametrize("invalid_raw,expected_exception_type", [
    ('{"a": 1}', ValueError),                # Không phải mảng
    ('[2, "123"]', ValueError),              # Thiếu phần tử
    ('[5, "123", "Action", {}]', ValueError),# Loại khung lạ (5)
    ('[2, "123", "Action", "not_dict"]', ValueError), # Tải không phải đối tượng
])
def test_parse_invalid_formats(invalid_raw, expected_exception_type):
    with pytest.raises(expected_exception_type):
        parse_message(invalid_raw)

