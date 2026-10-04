"""
Handler Heartbeat (SCRUM-117).

Luồng xử lý:
  - Tầng khung (handle_ocpp_message trong ocpp_handlers.py) đã gọi touch_last_seen
    trước khi dispatch vào handler này, cho MỌI tin nhắn từ trụ đã Accepted.
  - Handler chỉ có nhiệm vụ trả Heartbeat.conf gồm currentTime (giờ máy chủ UTC).

Lựa chọn thiết kế đã nêu:
  1. last_seen_at KHÔNG được cập nhật hai lần: khung cập nhật một lần trước dispatch;
     handler không gọi lại touch_last_seen.
  2. Payload Heartbeat không rỗng (ví dụ {"foo": "bar"}): OCPP 1.6 §4.6 nói
     payload BẮT BUỘC là {} — tuy nhiên đặc tả cũng yêu cầu bỏ qua trường thừa
     («Ignore unknown fields»). Lựa chọn ở đây: bỏ qua trường thừa, KHÔNG trả
     CALLERROR, để đảm bảo tương thích tối đa với firmware trụ cũ.
  3. Log dùng mức DEBUG (Heartbeat đến mỗi vài chục giây, không nên spam INFO).
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.services.ocpp_parser import pack_call_result

logger = logging.getLogger(__name__)


def handle_heartbeat(
    db: Session,
    charge_point_code: str,
    msg_id: str,
    payload: dict,  # noqa: ARG001 — payload được nhận nhưng trường thừa bị bỏ qua
) -> str:
    """
    Xử lý một CALL Heartbeat.

    last_seen_at đã được cập nhật ở tầng khung trước khi hàm này được gọi.
    Ở đây chỉ lấy giờ máy chủ UTC và trả Heartbeat.conf.

    Args:
        db:                 Phiên DB (không dùng trực tiếp ở đây, giữ để khớp chữ ký).
        charge_point_code:  Mã trụ lấy từ đường dẫn WebSocket.
        msg_id:             Message ID của CALL gốc.
        payload:            Payload của CALL (đặc tả là {}, trường thừa bị bỏ qua).

    Returns:
        Chuỗi JSON của CALLRESULT Heartbeat.conf.
    """
    # Lấy giờ máy chủ UTC — tuyệt đối không lấy từ payload (giờ trụ có thể lệch)
    current_time: str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # Mức DEBUG: Heartbeat đến rất thường xuyên, không log INFO để tránh spam
    logger.debug("Heartbeat charge_point=%s", charge_point_code)

    return pack_call_result(msg_id, {"currentTime": current_time})
