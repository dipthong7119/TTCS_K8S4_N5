"""Application handlers for the Sprint 2 OCPP 1.6J messages."""

import hashlib
import json
import logging
from datetime import UTC, datetime

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.charge_point import ChargePoint, Connector
from app.models.connector_error import ConnectorError
from app.models.id_tag import IdTag
from app.models.ocpp_message import OcppMessage
from app.models.station import Station
from app.models.user import User
from app.services.ocpp_parser import (
    OCPPError,
    pack_call_error,
    pack_call_result,
    parse_message,
)
from app.services.ocpp_status import map_status

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
IMPLEMENTED_ACTIONS = {"BootNotification", "Heartbeat", "StatusNotification", "Authorize"}
_missing_connector_logged_at: dict[tuple[str, int], datetime] = {}


def handle_ocpp_message(db: Session, charge_point_code: str, raw_msg: str) -> str:
    """Validate, dispatch, and persist one OCPP CALL with database idempotency."""
    try:
        msg_type, msg_id, action, payload, _, _ = _parse_for_handler(raw_msg)
    except OCPPError as exc:
        return pack_call_error(exc.message_id, exc.error_code, exc.description, exc.details)

    if msg_type in (3, 4):
        return ""
    if action not in SUPPORTED_ACTIONS:
        logger.warning("Unsupported OCPP action from %s: %s", charge_point_code, action)
        return pack_call_error(msg_id, "NotImplemented", f"Action {action} is not implemented")
    if action not in IMPLEMENTED_ACTIONS:
        logger.warning("OCPP action planned but not implemented for %s: %s", charge_point_code, action)
        return pack_call_error(msg_id, "NotImplemented", f"Action {action} is not implemented")

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
            logger.warning("OCPP message ID reused with different content from %s", charge_point_code)
        mark_charge_point_seen(db, charge_point_code)
        if action != "BootNotification" or _boot_was_accepted(existing.response_payload):
            point.status = "online"
        db.commit()
        if action in {"BootNotification", "Heartbeat", "StatusNotification"}:
            publish_charge_point_status(db, point.id)
        return existing.response_payload

    mark_charge_point_seen(db, charge_point_code)
    try:
        if action != "BootNotification":
            point.status = "online"
        response = _dispatch(db, point, msg_id, action, payload)
        record = OcppMessage(
            charge_point_code=charge_point_code,
            msg_id=msg_id,
            action=action,
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

    if action in {"BootNotification", "Heartbeat", "StatusNotification"}:
        publish_charge_point_status(db, point.id)
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


def mark_charge_point_seen(db: Session, charge_point_code: str) -> None:
    db.execute(
        update(ChargePoint)
        .where(ChargePoint.code == charge_point_code)
        .values(last_seen_at=func.current_timestamp())
        .execution_options(synchronize_session=False)
    )


def _dispatch(db: Session, point: ChargePoint, msg_id: str, action: str, payload: dict) -> str:
    if action == "BootNotification":
        return handle_boot_notification(db, point, msg_id, payload)
    if action == "Heartbeat":
        return handle_heartbeat(db, point, msg_id)
    if action == "StatusNotification":
        return handle_status_notification(db, point, msg_id, payload)
    if action == "Authorize":
        return handle_authorize(db, point, msg_id, payload)
    return pack_call_error(msg_id, "NotImplemented", f"Action {action} is not implemented")


def handle_boot_notification(db: Session, point: ChargePoint, msg_id: str, payload: dict) -> str:
    point.vendor = payload.get("chargePointVendor") or ""
    point.model = payload.get("chargePointModel") or ""
    point.firmware_version = payload.get("firmwareVersion") or ""
    station = db.query(Station).filter(Station.id == point.station_id).first()
    # A paused/maintenance station still connects so it can report state.
    # An administrative lock explicitly rejects the OCPP boot handshake.
    accepted = station is not None and station.status != "locked"
    point.status = "online" if accepted else "offline"
    return pack_call_result(
        msg_id,
        {
            "currentTime": _utc_timestamp(),
            "interval": settings.OCPP_HEARTBEAT_INTERVAL_SECONDS,
            "status": "Accepted" if accepted else "Rejected",
        },
    )


def handle_heartbeat(db: Session, point: ChargePoint, msg_id: str) -> str:
    # The router only lets an accepted booted connection reach this handler.
    point.status = "online"
    return pack_call_result(msg_id, {"currentTime": _utc_timestamp()})


def handle_status_notification(db: Session, point: ChargePoint, msg_id: str, payload: dict) -> str:
    connector_id = payload.get("connectorId")
    status_raw = payload.get("status")
    error_code = payload.get("errorCode")
    if type(connector_id) is not int or connector_id < 0:
        return pack_call_error(msg_id, "FormationViolation", "connectorId must be a non-negative integer")
    if not isinstance(status_raw, str) or not status_raw:
        return pack_call_error(msg_id, "FormationViolation", "status must be a non-empty string")
    if not isinstance(error_code, str) or not error_code:
        return pack_call_error(msg_id, "FormationViolation", "errorCode must be a non-empty string")

    if connector_id == 0:
        # OCPP connector 0 describes the charge point itself, not a connector row.
        point.ocpp_status = status_raw
        return pack_call_result(msg_id, {})

    connector = (
        db.query(Connector)
        .filter_by(charge_point_id=point.id, connector_id=connector_id)
        .first()
    )
    if connector is None:
        _warn_missing_connector(point.code, connector_id)
        return pack_call_result(msg_id, {})

    connector.ocpp_status = status_raw
    connector.status = map_status(status_raw)
    connector.error_code = error_code

    if error_code != "NoError":
        timestamp = _parse_timestamp(payload.get("timestamp")) or datetime.now(UTC).replace(tzinfo=None)
        db.add(
            ConnectorError(
                connector_id=connector.id,
                error_code=error_code,
                vendor_error_code=payload.get("vendorErrorCode"),
                info=payload.get("info"),
                timestamp=timestamp,
            )
        )
    return pack_call_result(msg_id, {})


def handle_authorize(db: Session, point: ChargePoint, msg_id: str, payload: dict) -> str:
    id_tag_value = payload.get("idTag")
    if not isinstance(id_tag_value, str) or not 1 <= len(id_tag_value) <= 20:
        return pack_call_error(msg_id, "FormationViolation", "idTag must contain 1 to 20 characters")

    tag = db.query(IdTag).filter(IdTag.id_tag == id_tag_value).first()
    status = "Invalid"
    if tag is None:
        logger.warning("Invalid OCPP idTag suffix=%s from %s", id_tag_value[-4:], point.code)
    else:
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
            status = "Blocked"
        elif _is_expired(tag.expiry_date):
            status = "Expired"
        else:
            status = "Accepted"

    id_tag_info = {"status": status}
    if tag and tag.expiry_date:
        expiry = tag.expiry_date
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        id_tag_info["expiryDate"] = expiry.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return pack_call_result(msg_id, {"idTagInfo": id_tag_info})


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
        logger.warning("Unregistered connector reported: charge_point=%s connector_id=%s", *key)
        _missing_connector_logged_at[key] = now


def publish_charge_point_status(db: Session, charge_point_id: int) -> None:
    point = db.query(ChargePoint).filter(ChargePoint.id == charge_point_id).first()
    if point is None:
        return
    station = db.query(Station).filter(Station.id == point.station_id).first()
    if station is None:
        return
    charge_points = []
    for item in db.query(ChargePoint).filter(ChargePoint.station_id == station.id).all():
        charge_points.append(
            {
                "id": item.id,
                "code": item.code,
                "status": item.status,
                "ocpp_status": item.ocpp_status,
                "vendor": item.vendor,
                "model": item.model,
                "firmware_version": item.firmware_version,
                "last_seen_at": item.last_seen_at.isoformat() if item.last_seen_at else None,
                "connectors": [
                    {
                        "id": connector.id,
                        "connector_id": connector.connector_id,
                        "status": connector.status,
                        "ocpp_status": connector.ocpp_status,
                        "error_code": connector.error_code,
                        "updated_at": connector.updated_at.isoformat(),
                    }
                    for connector in db.query(Connector)
                    .filter(Connector.charge_point_id == item.id)
                    .order_by(Connector.connector_id)
                    .all()
                ],
            }
        )
    from app.routers.monitoring import notify_status_change

    notify_status_change(station.id, charge_points, station.owner_id)
