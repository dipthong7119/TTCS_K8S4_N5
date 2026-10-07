"""Handler cho sự kiện StopTransaction (SCRUM-163)."""

import logging

from sqlalchemy.orm import Session

from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.services.billing import finalize_session_billing
from app.services.ocpp_handlers import (
    _normalize_meter_values,
    _parse_timestamp,
    _save_orphan_message,
    _store_meter_values,
)
from app.services.ocpp_parser import pack_call_error, pack_call_result
from app.services.session_energy import calculate_energy_kwh

logger = logging.getLogger(__name__)


def handle_stop_transaction(db: Session, point: ChargePoint, msg_id: str, payload: dict) -> str:
    transaction_id = payload.get("transactionId")
    meter_stop = payload.get("meterStop")
    ended_at = _parse_timestamp(payload.get("timestamp"))
    reason = payload.get("reason", "Other")
    if type(transaction_id) is not int or transaction_id <= 0:
        return pack_call_error(msg_id, "FormationViolation", "transactionId must be a positive integer")
    if type(meter_stop) is not int or meter_stop < 0:
        return pack_call_error(msg_id, "FormationViolation", "meterStop must be a non-negative integer")
    if ended_at is None or not isinstance(reason, str) or len(reason) > 50:
        return pack_call_error(msg_id, "FormationViolation", "A valid timestamp and reason are required")
    transaction_data = payload.get("transactionData", [])
    if not isinstance(transaction_data, list):
        return pack_call_error(msg_id, "FormationViolation", "transactionData must be an array")

    session = (
        db.query(ChargingSession)
        .filter_by(id=transaction_id, charge_point_id=point.id)
        .first()
    )
    if session is None:
        samples = _normalize_meter_values(transaction_data, ended_at)
        _save_orphan_message(
            db,
            point,
            action="StopTransaction",
            transaction_id=transaction_id,
            connector_number=None,
            reason="transaction_not_found",
            payload={
                "timestamp": ended_at.isoformat(),
                "meterStop": meter_stop,
                "reason": reason,
                "transactionData": samples,
            },
        )
        logger.warning(
            "Orphan StopTransaction received: charge_point=%s transaction_id=%s",
            point.code,
            transaction_id,
        )
        return pack_call_result(msg_id, {})
    
    if session.ended_at is not None:
        return pack_call_result(msg_id, {"idTagInfo": {"status": "Accepted"}})

    _store_meter_values(db, session, _normalize_meter_values(transaction_data, ended_at))
    session.meter_stop_wh = meter_stop
    session.ended_at = ended_at
    session.stop_reason = reason
    session.remote_stop_requested_at = None
    connector = (
        db.query(Connector)
        .filter_by(charge_point_id=point.id, connector_id=session.connector_number)
        .first()
    )
    calculated_kwh = calculate_energy_kwh(session.meter_start_wh, meter_stop)
    if calculated_kwh is not None:
        session.energy_kwh = calculated_kwh
        session.status = "completed"
        session.anomaly_reason = None
        finalize_session_billing(db, session, _normalize_meter_values(transaction_data, ended_at))
    else:
        session.energy_kwh = None
        session.status = "needs_review"
        session.anomaly_reason = "negative_kwh"
    if connector is not None:
        connector.status = "available"
        
    return pack_call_result(msg_id, {"idTagInfo": {"status": "Accepted"}})
