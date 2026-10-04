"""Application handlers for the Sprint 2 OCPP 1.6J messages."""

import hashlib
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.id_tag import IdTag
from app.models.meter_value import MeterValue
from app.models.ocpp_message import OcppMessage
from app.models.orphan_message import OrphanMessage
from app.models.station import Station
from app.models.user import User
from app.services.billing import finalize_session_billing
from app.services.ocpp_parser import (
    OCPPError,
    pack_call_error,
    pack_call_result,
    parse_message,
)
from app.services.session_energy import calculate_energy_kwh

logger = logging.getLogger(__name__)

SUPPORTED_ACTIONS = {
    "BootNotification",
    "Heartbeat",
    "StatusNotification",
    "Authorize",
    "StartTransaction",
    "MeterValues",
    "StopTransaction",
    "Reset",
}
IMPLEMENTED_ACTIONS = {
    "BootNotification",
    "Heartbeat",
    "StatusNotification",
    "Authorize",
    "StartTransaction",
    "MeterValues",
    "StopTransaction",
}
_missing_connector_logged_at: dict[tuple[str, int], datetime] = {}


def handle_ocpp_message(db: Session, charge_point_code: str, raw_msg: str) -> str:
    """Validate, dispatch, and persist one OCPP CALL with database idempotency."""
    try:
        msg_type, msg_id, action, payload, _, _ = _parse_for_handler(raw_msg)
    except OCPPError as exc:
        return pack_call_error(
            exc.message_id, exc.error_code, exc.description, exc.details
        )

    if msg_type in (3, 4):
        return ""
    point = db.query(ChargePoint).filter(ChargePoint.code == charge_point_code).first()
    if point is None:
        return pack_call_error(msg_id, "SecurityError", "Charge point not found")

    canonical_request = json.dumps(
        {"action": action, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    request_hash = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()

    # A repeated packet still proves the device is alive; touch one column and
    # return the durable response without executing the business handler again.
    existing = (
        db.query(OcppMessage)
        .filter_by(charge_point_code=charge_point_code, msg_id=msg_id)
        .first()
    )
    if existing:
        if existing.request_hash and existing.request_hash != request_hash:
            logger.warning(
                "OCPP message ID reused with different content from %s",
                charge_point_code,
            )
        touch_last_seen(db, charge_point_code)
        if action != "BootNotification" or _boot_was_accepted(
            existing.response_payload
        ):
            point.status = "online"
        db.commit()
        if action in {
            "BootNotification",
            "Heartbeat",
            "StatusNotification",
            "StartTransaction",
            "StopTransaction",
        }:
            publish_charge_point_status(db, point.id)
        if action in {"StartTransaction", "MeterValues", "StopTransaction"}:
            publish_session_update(db, point.id, action, payload)
        return existing.response_payload

    touch_last_seen(db, charge_point_code)
    try:
        is_implemented = action in SUPPORTED_ACTIONS and action in IMPLEMENTED_ACTIONS
        if is_implemented and action != "BootNotification":
            point.status = "online"
        if not is_implemented:
            logger.warning(
                "Unsupported OCPP action from %s: %s", charge_point_code, action
            )
            response = pack_call_error(
                msg_id, "NotImplemented", f"Action {action} is not implemented"
            )
        else:
            response = _dispatch(db, point, msg_id, action, payload)
        record = OcppMessage(
            charge_point_code=charge_point_code,
            msg_id=msg_id,
            action=action,
            request_payload=json.loads(raw_msg),
            response_payload=response,
            request_hash=request_hash,
        )
        db.add(record)
        db.commit()
    except IntegrityError:
        # Concurrent delivery of the same CALL: the composite DB index is the
        # source of truth, and the losing transaction must not retain side effects.
        db.rollback()
        existing = (
            db.query(OcppMessage)
            .filter_by(charge_point_code=charge_point_code, msg_id=msg_id)
            .first()
        )
        if existing:
            return existing.response_payload
        logger.exception("Could not persist OCPP message for %s", charge_point_code)
        return pack_call_error(msg_id, "InternalError", "Could not persist message")
    except (SQLAlchemyError, ValueError, TypeError):
        db.rollback()
        logger.exception(
            "OCPP handler failed for %s action %s", charge_point_code, action
        )
        return pack_call_error(msg_id, "InternalError", "Message processing failed")

    if action in {
        "BootNotification",
        "Heartbeat",
        "StatusNotification",
        "StartTransaction",
        "StopTransaction",
    }:
        publish_charge_point_status(db, point.id)
    if action in {"StartTransaction", "MeterValues", "StopTransaction"}:
        publish_session_update(db, point.id, action, payload)
    return response


def _parse_for_handler(raw_msg: str):
    try:
        return parse_message(raw_msg)
    except OCPPError:
        raise
    except (TypeError, ValueError) as exc:
        # Retain compatibility for parser errors raised by older call sites.
        text = str(exc).lower()
        code = (
            "FormationViolation"
            if "json" in text or "payload" in text
            else "ProtocolError"
        )
        raise OCPPError(code, str(exc)) from exc


def touch_last_seen(db: Session, charge_point_code: str) -> None:
    """Cập nhật last_seen_at cho mọi tin nhắn từ trụ bằng 1 câu UPDATE (không đọc-sửa-ghi)."""
    db.execute(
        update(ChargePoint)
        .where(ChargePoint.code == charge_point_code)
        .values(last_seen_at=func.current_timestamp())
        .execution_options(synchronize_session=False)
    )


def mark_charge_point_seen(db: Session, charge_point_code: str) -> None:
    db.execute(
        update(ChargePoint)
        .where(ChargePoint.code == charge_point_code)
        .values(last_seen_at=func.current_timestamp())
        .execution_options(synchronize_session=False)
    )


def _dispatch(
    db: Session, point: ChargePoint, msg_id: str, action: str, payload: dict
) -> str:
    if action == "BootNotification":
        from app.ocpp.handlers.boot_notification import (
            handle_boot_notification as new_handle_boot_notification,
        )

        return new_handle_boot_notification(db, point.code, msg_id, payload)
    if action == "Heartbeat":
        from app.ocpp.handlers.heartbeat import handle_heartbeat as new_handle_heartbeat

        return new_handle_heartbeat(db, point.code, msg_id, payload)
    if action == "StatusNotification":
        from app.ocpp.handlers.status_notification import (
            handle_status_notification as new_handle_status_notification,
        )

        return new_handle_status_notification(db, point.code, msg_id, payload)
    if action == "Authorize":
        return handle_authorize(db, point, msg_id, payload)
    if action == "StartTransaction":
        return handle_start_transaction(db, point, msg_id, payload)
    if action == "MeterValues":
        return handle_meter_values(db, point, msg_id, payload)
    if action == "StopTransaction":
        return handle_stop_transaction(db, point, msg_id, payload)
    return pack_call_error(
        msg_id, "NotImplemented", f"Action {action} is not implemented"
    )


def handle_authorize(
    db: Session, point: ChargePoint, msg_id: str, payload: dict
) -> str:
    id_tag_value = payload.get("idTag")
    if not isinstance(id_tag_value, str) or not 1 <= len(id_tag_value) <= 20:
        return pack_call_error(
            msg_id, "FormationViolation", "idTag must contain 1 to 20 characters"
        )

    tag, _, status = _authorize_tag(db, point, id_tag_value)

    id_tag_info = {"status": status}
    if tag and tag.expiry_date:
        expiry = tag.expiry_date
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        id_tag_info["expiryDate"] = (
            expiry.astimezone(UTC).isoformat().replace("+00:00", "Z")
        )
    return pack_call_result(msg_id, {"idTagInfo": id_tag_info})


def _authorize_tag(db: Session, point: ChargePoint, id_tag_value: str):
    tag = db.query(IdTag).filter(IdTag.id_tag == id_tag_value).first()
    if tag is None:
        logger.warning(
            "Invalid OCPP idTag suffix=%s from %s", id_tag_value[-4:], point.code
        )
        return None, None, "Invalid"

    user = db.query(User).filter(User.id == tag.user_id).first()
    station = db.query(Station).filter(Station.id == point.station_id).first()
    is_driver = user is not None and any(role.name == "driver" for role in user.roles)
    if (
        tag.is_blocked
        or user is None
        or not user.is_active
        or not is_driver
        or station is None
        or station.status != "active"
    ):
        return tag, user, "Blocked"
    if _is_expired(tag.expiry_date):
        return tag, user, "Expired"
    return tag, user, "Accepted"


def handle_start_transaction(
    db: Session, point: ChargePoint, msg_id: str, payload: dict
) -> str:
    connector_number = payload.get("connectorId")
    meter_start = payload.get("meterStart")
    id_tag_value = payload.get("idTag")
    started_at = _parse_timestamp(payload.get("timestamp"))
    if type(connector_number) is not int or connector_number <= 0:
        return pack_call_error(
            msg_id, "FormationViolation", "connectorId must be a positive integer"
        )
    if type(meter_start) is not int or meter_start < 0:
        return pack_call_error(
            msg_id, "FormationViolation", "meterStart must be a non-negative integer"
        )
    if (
        not isinstance(id_tag_value, str)
        or not 1 <= len(id_tag_value) <= 20
        or started_at is None
    ):
        return pack_call_error(
            msg_id, "FormationViolation", "idTag and a valid timestamp are required"
        )

    connector = (
        db.query(Connector)
        .filter_by(charge_point_id=point.id, connector_id=connector_number)
        .first()
    )
    tag, user, auth_status = _authorize_tag(db, point, id_tag_value)
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
        anomaly_reason=None
        if accepted
        else (
            "invalid_connector"
            if connector is None
            else f"start_{effective_status.lower()}"
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


def handle_stop_transaction(
    db: Session, point: ChargePoint, msg_id: str, payload: dict
) -> str:
    transaction_id = payload.get("transactionId")
    meter_stop = payload.get("meterStop")
    ended_at = _parse_timestamp(payload.get("timestamp"))
    reason = payload.get("reason", "Other")
    if type(transaction_id) is not int or transaction_id <= 0:
        return pack_call_error(
            msg_id, "FormationViolation", "transactionId must be a positive integer"
        )
    if type(meter_stop) is not int or meter_stop < 0:
        return pack_call_error(
            msg_id, "FormationViolation", "meterStop must be a non-negative integer"
        )
    if ended_at is None or not isinstance(reason, str) or len(reason) > 50:
        return pack_call_error(
            msg_id, "FormationViolation", "A valid timestamp and reason are required"
        )
    transaction_data = payload.get("transactionData", [])
    if not isinstance(transaction_data, list):
        return pack_call_error(
            msg_id, "FormationViolation", "transactionData must be an array"
        )

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

    _store_meter_values(
        db, session, _normalize_meter_values(transaction_data, ended_at)
    )
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
        finalize_session_billing(
            db, session, _normalize_meter_values(transaction_data, ended_at)
        )
    else:
        session.energy_kwh = None
        session.status = "needs_review"
        session.anomaly_reason = "negative_kwh"
    if connector is not None:
        connector.status = "available"
    return pack_call_result(msg_id, {"idTagInfo": {"status": "Accepted"}})


def handle_meter_values(
    db: Session, point: ChargePoint, msg_id: str, payload: dict
) -> str:
    connector_number = payload.get("connectorId")
    transaction_id = payload.get("transactionId")
    readings = payload.get("meterValue")
    if type(connector_number) is not int or connector_number < 0:
        return pack_call_error(
            msg_id, "FormationViolation", "connectorId must be a non-negative integer"
        )
    if not isinstance(readings, list):
        return pack_call_error(
            msg_id, "FormationViolation", "meterValue must be an array"
        )
    if transaction_id is not None and type(transaction_id) is not int:
        return pack_call_error(
            msg_id, "FormationViolation", "transactionId must be an integer"
        )

    query = db.query(ChargingSession).filter(
        ChargingSession.charge_point_id == point.id,
        ChargingSession.ended_at.is_(None),
    )
    if transaction_id is not None:
        query = query.filter(ChargingSession.id == transaction_id)
    else:
        query = query.filter(ChargingSession.connector_number == connector_number)
    session = query.order_by(ChargingSession.id.desc()).first()
    fallback_timestamp = _parse_timestamp(payload.get("timestamp"))
    samples = _normalize_meter_values(readings, fallback_timestamp)
    if session is None:
        _save_orphan_message(
            db,
            point,
            action="MeterValues",
            transaction_id=transaction_id,
            connector_number=connector_number,
            reason="no_active_session",
            payload={
                "connectorId": connector_number,
                "transactionId": transaction_id,
                "meterValue": samples,
            },
        )
        logger.warning(
            "Orphan MeterValues received: charge_point=%s connector=%s transaction_id=%s",
            point.code,
            connector_number,
            transaction_id,
        )
        return pack_call_result(msg_id, {})

    _store_meter_values(db, session, samples)
    return pack_call_result(msg_id, {})


KNOWN_MEASURANDS = {
    "Energy.Active.Import.Register",
    "Energy.Active.Import.Interval",
    "Energy.Active.Export.Register",
    "Energy.Active.Export.Interval",
    "Energy.Reactive.Import.Register",
    "Energy.Reactive.Import.Interval",
    "Energy.Reactive.Export.Register",
    "Energy.Reactive.Export.Interval",
    "Power.Active.Import",
    "Power.Active.Export",
    "Power.Active.Import.Offered",
    "Power.Active.Export.Offered",
    "Power.Factor",
    "Power.Reactive.Import",
    "Power.Reactive.Export",
    "Current.Import",
    "Current.Export",
    "Current.Offered",
    "Voltage",
    "Frequency",
    "SoC",
    "Temperature",
}

DEFAULT_METER_UNITS = {
    "Energy.Active.Import.Register": "Wh",
    "Energy.Active.Import.Interval": "Wh",
    "Energy.Active.Export.Register": "Wh",
    "Energy.Active.Export.Interval": "Wh",
    "Energy.Reactive.Import.Register": "varh",
    "Energy.Reactive.Import.Interval": "varh",
    "Energy.Reactive.Export.Register": "varh",
    "Energy.Reactive.Export.Interval": "varh",
    "Power.Active.Import": "W",
    "Power.Active.Export": "W",
    "Power.Active.Import.Offered": "W",
    "Power.Active.Export.Offered": "W",
    "Power.Reactive.Import": "var",
    "Power.Reactive.Export": "var",
    "Current.Import": "A",
    "Current.Export": "A",
    "Current.Offered": "A",
    "Voltage": "V",
    "Frequency": "Hz",
    "SoC": "%",
    "Temperature": "Celsius",
}


def _normalize_meter_values(
    readings: list, fallback_timestamp: datetime | None
) -> list[dict]:
    normalized = []
    for reading in readings:
        if not isinstance(reading, dict):
            continue
        measured_at = _parse_timestamp(reading.get("timestamp")) or fallback_timestamp
        samples = reading.get("sampledValue")
        if measured_at is None or not isinstance(samples, list):
            continue
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            measurand = sample.get("measurand") or "Energy.Active.Import.Register"
            raw_value = sample.get("value")
            if measurand not in KNOWN_MEASURANDS or isinstance(raw_value, bool):
                continue
            try:
                value = Decimal(str(raw_value))
            except (InvalidOperation, ValueError):
                continue
            if not value.is_finite():
                continue
            raw_unit = sample.get("unit")
            unit = (
                raw_unit
                if isinstance(raw_unit, str) and raw_unit
                else DEFAULT_METER_UNITS.get(measurand)
            )
            normalized.append(
                {
                    "measured_at": measured_at.isoformat(),
                    "measurand": measurand,
                    "value": str(value),
                    "unit": unit[:20] if unit else None,
                }
            )
    return normalized


def _store_meter_values(
    db: Session, session: ChargingSession, samples: list[dict]
) -> None:
    db.add_all(
        [
            MeterValue(
                session_id=session.id,
                measured_at=datetime.fromisoformat(sample["measured_at"]),
                measurand=sample["measurand"],
                value=Decimal(sample["value"]),
                unit=sample["unit"],
            )
            for sample in samples
        ]
    )


def _save_orphan_message(
    db: Session,
    point: ChargePoint,
    *,
    action: str,
    transaction_id: int | None,
    connector_number: int | None,
    reason: str,
    payload: dict,
) -> None:
    db.add(
        OrphanMessage(
            charge_point_code=point.code,
            action=action,
            transaction_id=transaction_id,
            connector_number=connector_number,
            reason=reason,
            payload=payload,
        )
    )


def _is_expired(expiry: datetime | None) -> bool:
    if expiry is None:
        return False
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    return expiry <= datetime.now(UTC)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _boot_was_accepted(response_payload: str) -> bool:
    try:
        _, _, _, result, _, _ = parse_message(response_payload)
    except (OCPPError, TypeError):
        return False
    return isinstance(result, dict) and result.get("status") == "Accepted"


def _warn_missing_connector(charge_point_code: str, connector_id: int) -> None:
    now = datetime.now(UTC)
    key = (charge_point_code, connector_id)
    previous = _missing_connector_logged_at.get(key)
    if previous is None or (now - previous).total_seconds() >= 60:
        logger.warning(
            "Unregistered connector reported: charge_point=%s connector_id=%s", *key
        )
        _missing_connector_logged_at[key] = now


def publish_charge_point_status(db: Session, charge_point_id: int) -> None:
    point = db.query(ChargePoint).filter(ChargePoint.id == charge_point_id).first()
    if point is None or point.station_id is None:
        return

    from sqlalchemy.orm import joinedload

    station = (
        db.query(Station)
        .options(joinedload(Station.charge_points).joinedload(ChargePoint.connectors))
        .filter(Station.id == point.station_id)
        .first()
    )

    if station is None:
        return

    from app.services.ocpp_status import station_status_payload

    payload = station_status_payload(station)

    from app.routers.monitoring import notify_status_change

    notify_status_change(station.id, payload["charge_points"], station.owner_id)


def publish_session_update(
    db: Session,
    charge_point_id: int,
    action: str,
    payload: dict,
) -> None:
    query = db.query(ChargingSession).filter(
        ChargingSession.charge_point_id == charge_point_id
    )
    if action == "StopTransaction":
        query = query.filter(ChargingSession.id == payload.get("transactionId"))
    elif action == "StartTransaction":
        query = query.filter(
            ChargingSession.connector_number == payload.get("connectorId")
        )
    else:
        transaction_id = payload.get("transactionId")
        if type(transaction_id) is int:
            query = query.filter(
                ChargingSession.id == transaction_id,
                ChargingSession.ended_at.is_(None),
            )
        else:
            query = query.filter(
                ChargingSession.connector_number == payload.get("connectorId"),
                ChargingSession.ended_at.is_(None),
            )
    session = query.order_by(ChargingSession.id.desc()).first()
    if session is None:
        return
    station = db.query(Station).filter(Station.id == session.station_id).first()
    from app.routers.monitoring import notify_session_change

    notify_session_change(
        session.user_id,
        station.owner_id if station is not None else None,
        session.id,
    )
