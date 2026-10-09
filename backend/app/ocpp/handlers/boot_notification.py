"""
Handler BootNotification (SCRUM-112 / SCRUM-113).

Task 1 — Lưu nhà sản xuất, mẫu trụ, firmware (T-16, S-08):
  - Đọc chargePointVendor, chargePointModel, firmwareVersion từ payload.
  - Trường nào thiếu → lưu NULL, KHÔNG từ chối tin nhắn.
  - Gửi lần hai trong cùng kết nối → chỉ cập nhật bản ghi cũ.

Task 2 — Trả Accepted/Rejected kèm khoảng nhịp tim cấu hình được (T-17, S-08):
  - Hàm thuần decide_boot_status() dễ unit-test độc lập.
  - Trạm locked → Rejected (trụ KHÔNG được online).
  - Trạm maintenance / active → Accepted.
  - interval ưu tiên cấu hình đã áp dụng riêng cho trụ.
  - Khi Rejected vẫn trả interval (đặc tả OCPP bắt buộc có trường này).
  - Khi Rejected vẫn lưu vendor/model/firmware (vận hành viên cần biết thiết bị nào đang cố nối).
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.services.charge_point_configuration import (
    activate_reboot_required_configurations,
    get_effective_heartbeat_interval,
)
from app.services.ocpp_parser import pack_call_result

logger = logging.getLogger(__name__)


def decide_boot_status(charge_point: ChargePoint, station: Station | None) -> str:
    """
    Quyết định Accepted hoặc Rejected dựa vào trạng thái trụ và trạm.

    Quy tắc:
      - station là None        → Rejected  (trụ không thuộc trạm nào — cấu hình sai)
      - station.status='locked'→ Rejected  (quản trị viên khoá toàn trạm)
      - còn lại (active, maintenance, paused, v.v.) → Accepted
        (trụ vẫn được báo trạng thái dù trạm tạm ngừng bảo trì)

    Giả định: schema Station có status ∈ {active, maintenance, locked}.
    Nếu sau này thêm status mới, rule mặc định là Accepted để tránh chặn thiết bị
    mà không có lý do rõ ràng — cần hỏi PO để thêm case Rejected tường minh.
    """
    if station is None:
        return "Rejected"
    if station.status == "locked":
        return "Rejected"
    return "Accepted"


def handle_boot_notification(
    db: Session,
    charge_point_code: str,
    msg_id: str,
    payload: dict,
) -> str:
    """
    Xử lý một CALL BootNotification.

    Luồng:
      1. Tải ChargePoint và Station từ DB.
      2. Cập nhật vendor / model / firmware_version (NULL nếu thiếu).
      3. Gọi decide_boot_status() để xác định Accepted/Rejected.
      4. Chỉ đặt status='online' khi Accepted.
      5. flush() để đảm bảo mọi thay đổi được lưu (kể cả khi Rejected).
      6. Trả CALLRESULT với status, currentTime (UTC ISO-8601), interval từ config.
    """
    # Tải trụ (đã được kiểm tra tồn tại bởi router trước khi vào đây)
    point = db.query(ChargePoint).filter(ChargePoint.code == charge_point_code).first()
    if not point:
        # Phòng trường hợp race condition — không nên xảy ra thông thường
        logger.error("BootNotification: charge point not found in DB: %s", charge_point_code)
        return ""

    station = db.query(Station).filter(Station.id == point.station_id).first()

    # --- Task 1: Lưu vendor / model / firmware (NULL nếu trường vắng mặt) ---
    # Dùng .get() trả None khi key thiếu; chuỗi rỗng "" cũng ánh xạ thành None
    # theo yêu cầu "Trường nào thiếu thì lưu NULL, KHÔNG từ chối tin nhắn".
    raw_vendor: str | None = payload.get("chargePointVendor")
    raw_model: str | None = payload.get("chargePointModel")
    raw_firmware: str | None = payload.get("firmwareVersion")

    point.vendor = raw_vendor if raw_vendor else None
    point.model = raw_model if raw_model else None
    point.firmware_version = raw_firmware if raw_firmware else None

    # --- Task 2: Quyết định status và cập nhật trạng thái trực tuyến ---
    status = decide_boot_status(point, station)

    if status == "Accepted":
        point.status = "online"
        # Boot kế tiếp xác nhận các cấu hình đang chờ khởi động lại.
        activate_reboot_required_configurations(db, point.id)
    else:
        point.status = "offline"
        for connector in point.connectors:
            connector.status = "unknown"
    # Khi Rejected: trụ offline, connector trở về unknown.
    # Vendor/model/firmware VẪN được lưu để vận hành viên biết thiết bị nào đang cố nối.

    # flush() — đẩy UPDATE vendor/model/firmware/status xuống transaction hiện tại
    # mà không commit (commit do caller — handle_ocpp_message — quyết định).
    db.flush()

    # --- Chuẩn bị CALLRESULT ---
    current_time = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    interval = get_effective_heartbeat_interval(db, point)

    # Log ngắn gọn theo yêu cầu: mã trụ, vendor, model, firmware, status trả về
    logger.info(
        "BootNotification charge_point=%s vendor=%s model=%s firmware=%s status=%s",
        charge_point_code,
        point.vendor,
        point.model,
        point.firmware_version,
        status,
    )

    return pack_call_result(
        msg_id,
        {
            "status": status,
            "currentTime": current_time,
            "interval": interval,
        },
    )
