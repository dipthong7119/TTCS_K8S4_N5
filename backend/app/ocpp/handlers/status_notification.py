"""
Handler cho sự kiện StatusNotification (SCRUM-119).
Chỉ cập nhật trạng thái của đầu nối trong bảng connectors. Cập nhật bằng 1 câu UPDATE.
"""

import logging

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.charge_point import ChargePoint, Connector
from app.ocpp.status_mapping import map_ocpp_status
from app.services.ocpp_parser import pack_call_error, pack_call_result

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

    from datetime import UTC, datetime

    from app.models.connector_error import ConnectorError

    error_code = payload.get("errorCode", "NoError")
    vendor_error_code = payload.get("vendorErrorCode")
    timestamp_raw = payload.get("timestamp")
    
    # Chuẩn hoá timestamp về UTC
    occurred_at = datetime.now(UTC).replace(tzinfo=None)
    if isinstance(timestamp_raw, str) and timestamp_raw:
        try:
            # Chuyển đổi "Z" thành "+00:00" để fromisoformat xử lý được
            dt = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
            occurred_at = dt.astimezone(UTC).replace(tzinfo=None)
        except ValueError:
            pass

    # Cập nhật bằng 1 câu truy vấn và lấy lại id của connector
    cp_subq = db.query(ChargePoint.id).filter(ChargePoint.code == charge_point_code).scalar_subquery()

    try:
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
            .returning(Connector.id)
            .execution_options(synchronize_session=False)
        )
        row = result.fetchone()
        
        if not row:
            logger.warning("Connector %s not found on %s, ignoring status update.", connector_id, charge_point_code)
            return pack_call_result(msg_id, {})
            
        connector_pk = row[0]
        
        # Ghi log lỗi nếu có lỗi
        if error_code != "NoError":
            db.add(ConnectorError(
                connector_id=connector_pk,
                error_code=error_code,
                vendor_error_code=vendor_error_code,
                occurred_at=occurred_at
            ))
            logger.warning("Connector error %s-%s: %s", charge_point_code, connector_id, error_code)

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Failed to update status for %s-%s: %s", charge_point_code, connector_id, e)

    return pack_call_result(msg_id, {})
