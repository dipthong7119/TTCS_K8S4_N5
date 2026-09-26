import json
from typing import Any


class OCPPError(Exception):
    def __init__(self, error_code: str, description: str, details: dict | None = None):
        self.error_code = error_code
        self.description = description
        self.details = details or {}
        super().__init__(f"{error_code}: {description}")

def parse_message(raw_msg: str) -> tuple[int, str, str | dict[str, Any] | None, dict[str, Any] | str | None, str | None, dict[str, Any] | None]:
    """
    Phân tích khung tin nhắn OCPP 1.6J.
    Trả về tuple chứa:
    - msg_type: int (2 cho CALL, 3 cho CALLRESULT, 4 cho CALLERROR)
    - msg_id: str (mã tin nhắn duy nhất)
    - action: str (tên hành động, chỉ cho CALL) hoặc request_id (cho CALLRESULT, CALLERROR)
    - payload: dict (dữ liệu payload cho CALL, CALLRESULT) hoặc error_code (cho CALLERROR)
    - error_description: str (chỉ cho CALLERROR)
    - error_details: dict (chỉ cho CALLERROR)
    """
    try:
        data = json.loads(raw_msg)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format")

    if not isinstance(data, list):
        raise ValueError("Message must be a JSON array")  # noqa: TRY004

    if len(data) < 3:
        raise ValueError("Message too short")

    msg_type = data[0]
    if not isinstance(msg_type, int) or msg_type not in (2, 3, 4):
        raise ValueError("Unknown message type")

    msg_id = str(data[1])

    if msg_type == 2:  # CALL
        if len(data) != 4:
            raise ValueError("CALL message must have exactly 4 elements")
        action = str(data[2])
        payload = data[3]
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")
        return msg_type, msg_id, action, payload, None, None

    elif msg_type == 3:  # CALLRESULT
        if len(data) != 3:
            raise ValueError("CALLRESULT message must have exactly 3 elements")
        payload = data[2]
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")
        # Với CALLRESULT, vị trí thứ 3 (index 2) là payload. 
        # Vị trí thứ 2 (index 1) là msg_id của CALL ban đầu.
        return msg_type, msg_id, None, payload, None, None

    elif msg_type == 4:  # CALLERROR
        if len(data) < 4 or len(data) > 5:
            raise ValueError("CALLERROR message must have 4 or 5 elements")
        error_code = str(data[2])
        error_description = str(data[3])
        error_details = data[4] if len(data) == 5 else {}
        if not isinstance(error_details, dict):
            raise ValueError("Error details must be a JSON object")
        return msg_type, msg_id, None, error_code, error_description, error_details

def pack_call(msg_id: str, action: str, payload: dict) -> str:
    """Đóng gói khung CALL"""
    return json.dumps([2, str(msg_id), str(action), payload])

def pack_call_result(msg_id: str, payload: dict) -> str:
    """Đóng gói khung CALLRESULT"""
    return json.dumps([3, str(msg_id), payload])

def pack_call_error(
    msg_id: str,
    error_code: str,
    error_description: str,
    error_details: dict | None = None,
) -> str:
    """Đóng gói khung CALLERROR"""
    return json.dumps([4, str(msg_id), str(error_code), str(error_description), error_details or {}])
