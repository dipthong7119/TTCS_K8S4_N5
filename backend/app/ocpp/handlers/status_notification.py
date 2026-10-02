"""
Handler cho sự kiện StatusNotification (SCRUM-119).
Chỉ cập nhật trạng thái của đầu nối trong bảng connectors. Cập nhật bằng 1 câu UPDATE.
"""

import logging
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.charge_point import ChargePoint, Connector
from app.ocpp.status_mapping import map_ocpp_status
from app.services.ocpp_parser import pack_call_result, pack_call_error

logger = logging.getLogger(__name__)

def handle_status_notification(db: Session, charge_point_code: str, msg_id: str, payload: dict) -> str:
    """Xử lý StatusNotification và cập nhật trạng thái đầu nối."""
    connector_id = payload.get("connectorId")
    status_raw = payload.get("status")

    if type(connector_id) is not int or connector_id < 0:
        logger.error("Invalid connectorId %s from %s", connector_id, charge_point_code)
        return pack_call_error(msg_id, "FormationViolation", "connectorId must be a non-negative integer")

    if not isinstance(status_raw, str) or not status_raw:
        logger.error("Invalid status %s from %s", status_raw, charge_point_code)
        return pack_call_error(msg_id, "FormationViolation", "status must be a non-empty string")

    # connectorId = 0 chỉ trạng thái của toàn trụ, không lưu vào connectors
    if connector_id == 0:
        logger.info("Charge point %s global status: %s", charge_point_code, status_raw)
        return pack_call_result(msg_id, {})

    internal_status = map_ocpp_status(status_raw).value

    # Cập nhật bằng 1 câu truy vấn để tối ưu hiệu suất (không read-modify-write)
    # Lồng query truy tìm ChargePoint.id từ charge_point_code
    cp_subq = db.query(ChargePoint.id).filter(ChargePoint.code == charge_point_code).scalar_subquery()

    result = db.execute(
        update(Connector)
        .where(
            Connector.charge_point_id == cp_subq,
            Connector.connector_id == connector_id
        )
        .values(
            status=internal_status,
            ocpp_status=status_raw
        )
        .execution_options(synchronize_session=False)
    )

    if result.rowcount == 0:
        logger.warning("Connector %s not found on %s, ignoring status update.", connector_id, charge_point_code)
    
    return pack_call_result(msg_id, {})
