"""
Handler cho sự kiện Heartbeat từ trụ sạc (SCRUM-117).
Cập nhật last_seen_at (tại router) và trả về currentTime (giờ máy chủ UTC).
"""

import logging
from datetime import UTC, datetime
from sqlalchemy.orm import Session
from app.services.ocpp_parser import pack_call_result

logger = logging.getLogger(__name__)

def handle_heartbeat(db: Session, charge_point_code: str, msg_id: str, payload: dict) -> str:
    """
    Xử lý bản tin Heartbeat. 
    Việc cập nhật last_seen_at đã được thực hiện ở tầng router qua hàm touch_last_seen.
    Ở đây chỉ cần trả về Heartbeat.conf gồm currentTime.
    """
    try:
        # Lấy giờ máy chủ chuẩn UTC (không dùng giờ của trụ), định dạng ISO 8601
        current_time = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        # Log ngắn gọn
        logger.info("Heartbeat received charge_point=%s", charge_point_code)
        
        return pack_call_result(msg_id, {"currentTime": current_time})
    except Exception as e:
        # Lỗi không làm sập kết nối WebSocket
        logger.error("Error processing Heartbeat charge_point=%s: %s", charge_point_code, e)
        return ""
