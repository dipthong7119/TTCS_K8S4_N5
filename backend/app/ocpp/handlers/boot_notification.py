"""
Handler tối thiểu cho BootNotification (giả định để Heartbeat tham chiếu).
"""

from sqlalchemy.orm import Session
from app.models.charge_point import ChargePoint
from app.services.ocpp_parser import pack_call_result

def handle_boot_notification(db: Session, charge_point_code: str, msg_id: str, payload: dict) -> str:
    """Bản tối thiểu xử lý BootNotification."""
    return pack_call_result(msg_id, {"status": "Accepted", "interval": 300, "currentTime": "2026-10-02T00:00:00.000Z"})
