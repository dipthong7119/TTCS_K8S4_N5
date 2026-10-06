"""Application handlers for the Sprint 2 OCPP 1.6J messages."""

import hashlib
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.meter_value import MeterValue
from app.models.ocpp_message import OcppMessage
from app.models.orphan_message import OrphanMessage
from app.models.station import Station
from app.services.billing import finalize_session_billing
from app.services.ocpp_parser import (
    OCPPError,
    pack_call_error,
    pack_call_result,
    parse_message,
)
from app.services.ocpp_status import is_charge_point_stale, station_status_payload
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
        return pack_call_error(exc.message_id, exc.error_code, exc.description, exc.details)

    if msg_type in (3, 4):
        return ""
    point = db.query(ChargePoint).filter(ChargePoint.code == charge_point_code).first()
    if point is None:
        return pack_call_error(msg_id, "SecurityError", "Charge point not found")

    # A returning device must report fresh connector states even if the offline
    # sweep has not run since the heartbeat deadline expired.
    if point.status == "offline" or is_charge_point_stale(point.last_seen_at):
        for connector in point.connectors:
            connector.status = "unknown"

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
            logger.warning("OCPP message ID reused with different content from %s", charge_point_code)
        touch_last_seen(db, charge_point_code)
        if action != "BootNotification" or _boot_was_accepted(existing.response_payload):
            point.status = "online"
        db.commit()
        if action in {"BootNotification", "Heartbeat", "StatusNotification", "StartTransaction", "StopTransaction"}:
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
            logger.warning("Unsupported OCPP action from %s: %s", charge_point_code, action)
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
        logger.exception("OCPP handler failed for %s action %s", charge_point_code, action)
        return pack_call_error(msg_id, "InternalError", "Message processing failed")

    if action in {"BootNotification", "Heartbeat", "StatusNotification", "StartTransaction", "StopTransaction"}:
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
        code = "FormationViolation" if "json" in text or "payload" in text else "ProtocolError"
        raise OCPPError(code, str(exc)) from exc


def touch_last_seen(db: Session, charge_point_code: str) -> None:
    """Cập nhật last_seen_at cho mọi tin nhắn từ trụ bằng 1 câu UPDATE (không đọc-sửa-ghi)."""
    db.execute(
        text("UPDATE charge_points SET last_seen_at = CURRENT_TIMESTAMP WHERE code = :code"),
        {"code": charge_point_code},
    )


def mark_charge_point_seen(db: Session, charge_point_code: str) -> None:
    touch_last_seen(db, charge_point_code)

def _dispatch(db: Session, point: ChargePoint, msg_id: str, action: str, payload: dict) -> str:
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
        from app.ocpp.handlers.authorize import handle_authorize as new_handle_authorize
        return new_handle_authorize(db, point, msg_id, payload)
    if action == "StartTransaction":
        from app.ocpp.handlers.start_transaction import handle_start_transaction as new_handle_start_transaction
        return new_handle_start_transaction(db, point, msg_id, payload)
    if action == "MeterValues":
        from app.ocpp.handlers.meter_values import handle_meter_values as new_handle_meter_values
        return new_handle_meter_values(db, point, msg_id, payload)
    if action == "StopTransaction":
        from app.ocpp.handlers.stop_transaction import handle_stop_transaction as new_handle_stop_transaction
        return new_handle_stop_transaction(db, point, msg_id, payload)
    return pack_call_error(msg_id, "NotImplemented", f"Action {action} is not implemented")



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
        logger.warning("Unregistered connector reported: charge_point=%s connector_id=%s", *key)
        _missing_connector_logged_at[key] = now


def publish_charge_point_status(db: Session, charge_point_id: int) -> None:
    from app.routers.monitoring import notify_status_change, sse_clients

    if not sse_clients:
        return
    # A heartbeat must not issue a separate connector query for every point.
    # Load the authoritative station snapshot in one query, as the tree API does.
    station_id = db.query(ChargePoint.station_id).filter(ChargePoint.id == charge_point_id).scalar_subquery()
    station = (
        db.query(Station)
        .options(joinedload(Station.charge_points).joinedload(ChargePoint.connectors))
        .filter(Station.id == station_id)
        .first()
    )
    if station is None:
        return
    snapshot = station_status_payload(station)
    notify_status_change(station.id, snapshot["charge_points"], station.owner_id)


def publish_session_update(
    db: Session,
    charge_point_id: int,
    action: str,
    payload: dict,
) -> None:
    query = db.query(ChargingSession).filter(ChargingSession.charge_point_id == charge_point_id)
    if action == "StopTransaction":
        query = query.filter(ChargingSession.id == payload.get("transactionId"))
    elif action == "StartTransaction":
        query = query.filter(ChargingSession.connector_number == payload.get("connectorId"))
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
