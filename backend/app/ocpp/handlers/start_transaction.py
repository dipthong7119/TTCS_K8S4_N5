"""Handler cho sự kiện StartTransaction (SCRUM-162)."""

import logging

from sqlalchemy.orm import Session

from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.ocpp.handlers.authorize import authorize_tag
from app.services.ocpp_handlers import _parse_timestamp
from app.services.ocpp_parser import pack_call_error, pack_call_result

logger = logging.getLogger(__name__)


def handle_start_transaction(db: Session, point: ChargePoint, msg_id: str, payload: dict) -> str:
    """Xử lý sự kiện StartTransaction từ trụ sạc."""
    connector_number = payload.get("connectorId")
    meter_start = payload.get("meterStart")
    id_tag_value = payload.get("idTag")
    started_at = _parse_timestamp(payload.get("timestamp"))
    
    if type(connector_number) is not int or connector_number <= 0:
        return pack_call_error(msg_id, "FormationViolation", "connectorId must be a positive integer")
    if type(meter_start) is not int or meter_start < 0:
        return pack_call_error(msg_id, "FormationViolation", "meterStart must be a non-negative integer")
    if not isinstance(id_tag_value, str) or not 1 <= len(id_tag_value) <= 20 or started_at is None:
        return pack_call_error(msg_id, "FormationViolation", "idTag and a valid timestamp are required")

    connector = db.query(Connector).filter_by(
        charge_point_id=point.id, connector_id=connector_number
    ).first()
    
    tag, user, auth_status = authorize_tag(db, point, id_tag_value)
    station = db.query(Station).filter(Station.id == point.station_id).first()
    effective_status = auth_status if connector is not None else "Invalid"
    accepted = effective_status == "Accepted"

    if accepted:
        previous = (
            db.query(ChargingSession)
            .filter(
                ChargingSession.charge_point_id == point.id,
                ChargingSession.connector_number == connector_number,
                ChargingSession.ended_at.is_(None),
            )
            .order_by(ChargingSession.id.desc())
            .first()
        )
        if previous is not None:
            previous.ended_at = max(started_at, previous.started_at)
            previous.stop_reason = "ConcurrentStart"
            previous.status = "anomaly"
            previous.anomaly_reason = "concurrent_start"
            logger.warning(
                "Closing previous session after concurrent StartTransaction: charge_point=%s connector=%s session=%s",
                point.code,
                connector_number,
                previous.id,
            )

    session = ChargingSession(
        charge_point_id=point.id,
        charge_point_code=point.code,
        station_id=station.id if station else None,
        station_name=station.name if station else "",
        connector_number=connector_number,
        user_id=user.id if user else None,
        driver_name=user.full_name if user else None,
        id_tag_id=tag.id if tag else None,
        id_tag=id_tag_value,
        meter_start_wh=meter_start,
        started_at=started_at,
        ended_at=None if accepted else started_at,
        status="active" if accepted else "needs_review",
        anomaly_reason=None if accepted else (
            "invalid_connector" if connector is None else f"start_{effective_status.lower()}"
        ),
    )
    db.add(session)
    db.flush()
    
    if accepted and connector is not None:
        connector.status = "charging"
        
    return pack_call_result(
        msg_id,
        {"transactionId": session.id, "idTagInfo": {"status": effective_status}},
    )
