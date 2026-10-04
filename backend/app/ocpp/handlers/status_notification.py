"""Handler cho sự kiện StatusNotification (SCRUM-119)."""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models.charge_point import ChargePoint, Connector
from app.models.connector_error import ConnectorError
from app.ocpp.status_mapping import map_ocpp_status
from app.ocpp.warning_throttler import unknown_connector_throttler
from app.services.ocpp_parser import pack_call_error, pack_call_result

logger = logging.getLogger(__name__)


def handle_status_notification(
    db: Session, charge_point_code: str, msg_id: str, payload: dict
) -> str:
    """Update connector state and append an error record when needed."""
    connector_id = payload.get("connectorId")
    status_raw = payload.get("status")

    if type(connector_id) is not int or connector_id < 0:
        logger.error("Invalid connectorId %s from %s", connector_id, charge_point_code)
        return pack_call_error(
            msg_id, "FormationViolation", "connectorId must be a non-negative integer"
        )

    if not isinstance(status_raw, str) or not status_raw:
        logger.error("Invalid status %s from %s", status_raw, charge_point_code)
        return pack_call_error(
            msg_id, "FormationViolation", "status must be a non-empty string"
        )

    # connectorId = 0 reports the charge point status, not a connector row.
    if connector_id == 0:
        logger.info("Charge point %s global status: %s", charge_point_code, status_raw)
        return pack_call_result(msg_id, {})

    internal_status = map_ocpp_status(status_raw).value
    error_code = payload.get("errorCode", "NoError")
    vendor_error_code = payload.get("vendorErrorCode")
    timestamp_raw = payload.get("timestamp")

    occurred_at = datetime.now(UTC).replace(tzinfo=None)
    if isinstance(timestamp_raw, str) and timestamp_raw:
        try:
            parsed_timestamp = datetime.fromisoformat(
                timestamp_raw.replace("Z", "+00:00")
            )
            occurred_at = parsed_timestamp.astimezone(UTC).replace(tzinfo=None)
        except ValueError:
            pass

    charge_point_id = (
        db.query(ChargePoint.id)
        .filter(ChargePoint.code == charge_point_code)
        .scalar_subquery()
    )
    result = db.execute(
        update(Connector)
        .where(
            Connector.charge_point_id == charge_point_id,
            Connector.connector_id == connector_id,
        )
        .values(status=internal_status, ocpp_status=status_raw)
        .returning(Connector.id)
        .execution_options(synchronize_session=False)
    )
    connector = result.first()

    if connector is None:
        # Lấy số đầu nối đã khai (số dòng của trụ này trong bảng connectors)
        declared_count = (
            db.query(func.count(Connector.id))
            .filter(Connector.charge_point_id == charge_point_id)
            .scalar()
        )

        if unknown_connector_throttler.should_warn(
            charge_point_code,
            connector_id,
            settings.UNKNOWN_CONNECTOR_WARN_INTERVAL,
        ):
            logger.warning(
                "Đầu nối chưa khai báo: Trụ %s gửi trạng thái cho đầu nối %s, nhưng chỉ khai %s đầu nối.",
                charge_point_code,
                connector_id,
                declared_count,
            )
        return pack_call_result(msg_id, {})

    if error_code != "NoError":
        db.add(
            ConnectorError(
                connector_id=connector[0],
                error_code=error_code,
                vendor_error_code=vendor_error_code,
                occurred_at=occurred_at,
            )
        )
        logger.warning(
            "Connector error %s-%s: %s", charge_point_code, connector_id, error_code
        )

    return pack_call_result(msg_id, {})
