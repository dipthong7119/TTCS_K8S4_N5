"""StopTransaction, kể cả tin tới muộn sau ngoại tuyến (T-38, T-45)."""

import logging
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.meter_value import MeterValue
from app.ocpp.session_statuses import OPEN_SESSION_STATUSES
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


def handle_stop_transaction(
    db: Session,
    point: ChargePoint,
    msg_id: str,
    payload: dict[str, Any],
) -> str:
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
        .with_for_update()
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
        if session.meter_stop_wh != meter_stop:
            logger.warning(
                "StopTransaction replay differs: cp=%s connector=%s transaction=%s old_meter_stop=%s new_meter_stop=%s",
                point.code,
                session.connector_number,
                transaction_id,
                session.meter_stop_wh,
                meter_stop,
            )
        return pack_call_result(msg_id, {"idTagInfo": {"status": "Accepted"}})

    if session.status not in OPEN_SESSION_STATUSES:
        logger.warning(
            "StopTransaction ignored for non-open session: cp=%s connector=%s transaction=%s status=%s",
            point.code,
            session.connector_number,
            transaction_id,
            session.status,
        )
        return pack_call_result(msg_id, {"idTagInfo": {"status": "Accepted"}})

    calculated_kwh = calculate_energy_kwh(session.meter_start_wh, meter_stop)
    timestamp_before_start = ended_at < session.started_at
    needs_review = timestamp_before_start or calculated_kwh is None
    final_status = "needs_review" if needs_review else "completed"
    if timestamp_before_start:
        review_reason = session.review_reason or "stop_timestamp_before_start"
        anomaly_reason = "stop_timestamp_before_start"
    elif calculated_kwh is None:
        review_reason = session.review_reason or "negative_kwh"
        anomaly_reason = "negative_kwh"
    else:
        review_reason = (
            None
            if session.review_reason == "connector_available_after_reconnect"
            else session.review_reason
        )
        anomaly_reason = None

    # Chỉ đóng đúng một phiên còn mở của trụ gửi tin.
    changed = db.execute(
        update(ChargingSession)
        .where(
            ChargingSession.id == transaction_id,
            ChargingSession.charge_point_id == point.id,
            ChargingSession.ended_at.is_(None),
            ChargingSession.status.in_(OPEN_SESSION_STATUSES),
        )
        .values(
            meter_stop_wh=meter_stop,
            ended_at=ended_at,
            stop_reason=reason,
            remote_stop_requested_at=None,
            energy_kwh=calculated_kwh,
            status=final_status,
            review_reason=review_reason,
            anomaly_reason=anomaly_reason,
        )
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        logger.info(
            "StopTransaction already settled: cp=%s connector=%s transaction=%s",
            point.code,
            session.connector_number,
            transaction_id,
        )
        return pack_call_result(msg_id, {"idTagInfo": {"status": "Accepted"}})

    # Làm mới object để hàm tính tiền dùng đúng dữ liệu vừa cập nhật.
    db.refresh(session)
    if timestamp_before_start:
        logger.warning(
            "StopTransaction timestamp precedes session start: cp=%s connector=%s transaction=%s started_at=%s stopped_at=%s",
            point.code,
            session.connector_number,
            transaction_id,
            session.started_at.isoformat(),
            ended_at.isoformat(),
        )
    if calculated_kwh is None:
        logger.warning(
            "StopTransaction meter regressed: cp=%s connector=%s transaction=%s meter_start=%s meter_stop=%s",
            point.code,
            session.connector_number,
            transaction_id,
            session.meter_start_wh,
            meter_stop,
        )

    _store_meter_values(db, session, _normalize_meter_values(transaction_data, ended_at))
    db.flush()
    connector = (
        db.query(Connector)
        .filter_by(charge_point_id=point.id, connector_id=session.connector_number)
        .first()
    )
    if calculated_kwh is not None:
        # Billing uses persisted readings, including samples received before the
        # outage. Skipping a duplicate must not lose its time-band boundary.
        readings = (
            db.query(MeterValue)
            .filter_by(session_id=session.id, measurand="Energy.Active.Import.Register")
            .order_by(MeterValue.measured_at, MeterValue.id)
            .all()
        )
        finalize_session_billing(db, session, [
            {"measured_at": row.measured_at.isoformat(), "measurand": row.measurand,
             "value": str(row.value), "unit": row.unit}
            for row in readings
        ])
    if connector is not None:
        connector.status = "available"
        
    return pack_call_result(msg_id, {"idTagInfo": {"status": "Accepted"}})
