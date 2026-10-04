"""Handler cho sự kiện Authorize (SCRUM-132)."""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.charge_point import ChargePoint
from app.models.id_tag import IdTag
from app.models.station import Station
from app.models.user import User
from app.services.ocpp_parser import pack_call_error, pack_call_result

logger = logging.getLogger(__name__)


def mask_id_tag(id_tag: str) -> str:
    """Che mã thẻ RFID (chỉ giữ 4 ký tự cuối) dùng trong toàn bộ log."""
    if not isinstance(id_tag, str):
        return ""
    if len(id_tag) <= 4:
        return id_tag
    return "*" * (len(id_tag) - 4) + id_tag[-4:]


def _is_expired(expiry: datetime | None) -> bool:
    """Kiểm tra thẻ đã hết hạn chưa so với giờ UTC hiện tại."""
    if expiry is None:
        return False
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    return expiry <= datetime.now(UTC)


def decide_authorize_status(tag: IdTag | None, user: User | None, is_driver: bool, station: Station | None) -> str:
    """
    Hàm thuần xác định trạng thái thẻ theo thứ tự ưu tiên:
    Invalid → Blocked (trạm ngừng) → Blocked (thẻ khoá/tài xế inactive) → Expired → Accepted.
    """
    if tag is None:
        return "Invalid"
    if station is None or station.status != "active":
        return "Blocked"
    if tag.is_blocked or user is None or not user.is_active or not is_driver:
        return "Blocked"
    if _is_expired(tag.expiry_date):
        return "Expired"
    return "Accepted"


def authorize_tag(db: Session, point: ChargePoint, id_tag_value: str) -> tuple[IdTag | None, User | None, str]:
    """
    Tra cứu DB và xác thực thẻ. Hàm này được dùng chung cho Authorize và StartTransaction.
    """
    tag = db.query(IdTag).filter(IdTag.id_tag == id_tag_value).first()
    
    user = None
    is_driver = False
    if tag is not None:
        user = db.query(User).filter(User.id == tag.user_id).first()
        is_driver = user is not None and any(role.name == "driver" for role in user.roles)
        
    station = db.query(Station).filter(Station.id == point.station_id).first()
    
    status = decide_authorize_status(tag, user, is_driver, station)
    
    masked_tag = mask_id_tag(id_tag_value)
    if status == "Invalid":
        logger.warning("Invalid OCPP idTag %s from %s", masked_tag, point.code)
    else:
        logger.info("OCPP Authorize idTag %s from %s -> %s", masked_tag, point.code, status)

    return tag, user, status


def handle_authorize(db: Session, point: ChargePoint, msg_id: str, payload: dict) -> str:
    """Xử lý bản tin Authorize."""
    id_tag_value = payload.get("idTag")
    if not isinstance(id_tag_value, str) or not 1 <= len(id_tag_value) <= 20:
        return pack_call_error(msg_id, "FormationViolation", "idTag must contain 1 to 20 characters")

    tag, _, status = authorize_tag(db, point, id_tag_value)

    id_tag_info = {"status": status}
    if tag and tag.expiry_date:
        expiry = tag.expiry_date
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        id_tag_info["expiryDate"] = expiry.astimezone(UTC).isoformat().replace("+00:00", "Z")
        
    return pack_call_result(msg_id, {"idTagInfo": id_tag_info})
