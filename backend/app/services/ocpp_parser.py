import json
from typing import Any


class OCPPError(ValueError):
    def __init__(
        self,
        error_code: str,
        description: str,
        details: dict | None = None,
        message_id: str = "",
    ):
        self.error_code = error_code
        self.description = description
        self.details = details or {}
        self.message_id = message_id
        super().__init__(f"{error_code}: {description}")


def parse_message(
    raw_msg: str,
) -> tuple[int, str, str | dict[str, Any] | None, dict[str, Any] | str | None, str | None, dict[str, Any] | None]:
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
    except (json.JSONDecodeError, TypeError) as exc:
        raise OCPPError("FormationViolation", "Invalid JSON format") from exc

    if not isinstance(data, list):
        raise OCPPError("FormationViolation", "Message must be a JSON array")

    message_id = data[1] if len(data) > 1 else ""
    if not isinstance(message_id, str) or len(message_id) > 50:
        raise OCPPError("FormationViolation", "Message ID must be a string of at most 50 characters")

    msg_type = data[0]
    if type(msg_type) is not int or msg_type not in (2, 3, 4):
        raise OCPPError("ProtocolError", "Unknown message type", message_id=message_id)

    msg_id = message_id

    if msg_type == 2:  # CALL
        if len(data) != 4:
            raise OCPPError("FormationViolation", "CALL message must have exactly 4 elements", message_id=msg_id)
        action = data[2]
        if not isinstance(action, str) or not action:
            raise OCPPError("FormationViolation", "CALL action must be a non-empty string", message_id=msg_id)
        payload = data[3]
        if not isinstance(payload, dict):
            raise OCPPError("FormationViolation", "Payload must be a JSON object", message_id=msg_id)
        return msg_type, msg_id, action, payload, None, None

    if msg_type == 3:  # CALLRESULT
        if len(data) != 3:
            raise OCPPError("FormationViolation", "CALLRESULT must have exactly 3 elements", message_id=msg_id)
        payload = data[2]
        if not isinstance(payload, dict):
            raise OCPPError("FormationViolation", "Payload must be a JSON object", message_id=msg_id)
        # Với CALLRESULT, vị trí thứ 3 (index 2) là payload. 
        # Vị trí thứ 2 (index 1) là msg_id của CALL ban đầu.
        return msg_type, msg_id, None, payload, None, None

    if msg_type == 4:  # CALLERROR
        if len(data) != 5:
            raise OCPPError("FormationViolation", "CALLERROR must have exactly 5 elements", message_id=msg_id)
        error_code = data[2]
        error_description = data[3]
        if not isinstance(error_code, str) or not error_code:
            raise OCPPError("FormationViolation", "CALLERROR code must be a non-empty string", message_id=msg_id)
        if not isinstance(error_description, str):
            raise OCPPError("FormationViolation", "CALLERROR description must be a string", message_id=msg_id)
        error_details = data[4]
        if not isinstance(error_details, dict):
            raise OCPPError("FormationViolation", "Error details must be a JSON object", message_id=msg_id)
        return msg_type, msg_id, None, error_code, error_description, error_details

    raise OCPPError("ProtocolError", "Unknown message type", message_id=msg_id)

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
