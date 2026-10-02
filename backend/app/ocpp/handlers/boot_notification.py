"""
Handler cho BootNotification (SCRUM-113).
Xử lý lưu vendor, model, firmware_version và quyết định trạng thái Accepted/Rejected.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.services.ocpp_parser import pack_call_result

logger = logging.getLogger(__name__)

def decide_boot_status(charge_point: ChargePoint, station: Station | None) -> str:
    """
    Quyết định trạng thái Accepted hoặc Rejected dựa trên trạng thái của trụ và trạm.
    Trạm hoạt động hoặc tạm ngừng (bảo trì) thì Accepted.
    Trạm bị khoá (locked) hoặc không tồn tại thì Rejected.
    """
    if station is None:
        return "Rejected"
    if station.status == "locked":
        return "Rejected"
    return "Accepted"

def handle_boot_notification(db: Session, charge_point_code: str, msg_id: str, payload: dict) -> str:
    """Xử lý BootNotification."""
    # Lấy thông tin trụ và trạm
    point = db.query(ChargePoint).filter(ChargePoint.code == charge_point_code).first()
    if not point:
        logger.error("Charge point not found: %s", charge_point_code)
        return ""
        
    station = db.query(Station).filter(Station.id == point.station_id).first()

    # Cập nhật vendor, model, firmware (như giả định là đã có logic này)
    point.vendor = payload.get("chargePointVendor") or None
    point.model = payload.get("chargePointModel") or None
    point.firmware_version = payload.get("firmwareVersion") or None

    # Quyết định status
    status = decide_boot_status(point, station)
    
    # Cập nhật trạng thái trực tuyến nếu Accepted
    if status == "Accepted":
        point.status = "online"
    # Giả định: nếu Rejected, trụ không được trực tuyến (vẫn lưu vendor/model trên)
    
    # Chuẩn bị phản hồi
    current_time = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    interval = settings.HEARTBEAT_INTERVAL

    logger.info("BootNotification charge_point=%s status=%s", charge_point_code, status)
    
    return pack_call_result(
        msg_id, 
        {
            "status": status,
            "currentTime": current_time,
            "interval": interval
        }
    )
