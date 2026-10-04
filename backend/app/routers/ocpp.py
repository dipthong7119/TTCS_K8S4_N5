"""OCPP 1.6J WebSocket endpoint for registered charge points (T-12–T-15)."""

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.database import SessionLocal
from app.models.charge_point import ChargePoint
from app.services.connection_manager import manager
from app.services.ocpp_handlers import handle_ocpp_message, touch_last_seen
from app.services.ocpp_parser import OCPPError, pack_call_error, parse_message

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ocpp/{charge_point_code}")
async def ocpp_websocket_endpoint(websocket: WebSocket, charge_point_code: str):
    requested_protocols = [
        protocol.strip()
        for protocol in websocket.headers.get("sec-websocket-protocol", "").split(",")
    ]
    if "ocpp1.6" not in requested_protocols:
        logger.warning(
            "Rejected charge point connection for unsupported subprotocol: code=%s ip=%s",
            charge_point_code,
            websocket.client.host if websocket.client else "unknown",
        )
        await websocket.close(code=1002, reason="Unsupported protocol")
        return

    with SessionLocal() as db:
        charge_point_exists = (
            db.query(ChargePoint.id).filter(ChargePoint.code == charge_point_code).first()
            is not None
        )
    if not charge_point_exists:
        logger.warning(
            "Rejected unknown charge point: code=%s ip=%s",
            charge_point_code,
            websocket.client.host if websocket.client else "unknown",
        )
        await websocket.close(code=1008, reason="Connection rejected")
        return

    await websocket.accept(subprotocol="ocpp1.6")
    await manager.connect(charge_point_code, websocket)
    logger.info("Charge point connected: %s", charge_point_code)
    boot_accepted = False

    try:
        while True:
            raw_msg = await websocket.receive_text()
            try:
                message = parse_message(raw_msg)
            except OCPPError as exc:
                with SessionLocal() as db:
                    touch_last_seen(db, charge_point_code)
                    db.commit()
                await websocket.send_text(
                    pack_call_error(exc.message_id, exc.error_code, exc.description, exc.details)
                )
                continue

            msg_type, msg_id, action, payload, error_code, error_description, error_details = (
                _normalize_parsed_message(message)
            )

            if msg_type == 3:
                with SessionLocal() as db:
                    touch_last_seen(db, charge_point_code)
                    db.commit()
                matched = await manager.resolve_call_result(
                    charge_point_code, msg_id, payload, websocket
                )
                if not matched:
                    logger.warning("Unmatched OCPP CALLRESULT from %s", charge_point_code)
                continue
            if msg_type == 4:
                with SessionLocal() as db:
                    touch_last_seen(db, charge_point_code)
                    db.commit()
                matched = await manager.resolve_call_error(
                    charge_point_code,
                    msg_id,
                    error_code,
                    error_description,
                    error_details,
                    websocket,
                )
                if not matched:
                    logger.warning("Unmatched OCPP CALLERROR from %s", charge_point_code)
                continue

            if not boot_accepted and action != "BootNotification":
                with SessionLocal() as db:
                    touch_last_seen(db, charge_point_code)
                    db.commit()
                await websocket.send_text(
                    pack_call_error(msg_id, "SecurityError", "BootNotification is required first")
                )
                continue

            with SessionLocal() as db:
                response = handle_ocpp_message(db, charge_point_code, raw_msg)

            try:
                response_frame = parse_message(response) if response else None
            except OCPPError:
                response_frame = None
            if action == "BootNotification" and response_frame and response_frame[0] == 3 and isinstance(response_frame[3], dict):
                boot_accepted = response_frame[3].get("status") == "Accepted"

            # Do not deliver work from a replaced socket to its successor.
            if manager.active_connections.get(charge_point_code) is websocket and response:
                await websocket.send_text(response)

    except WebSocketDisconnect:
        logger.info("Charge point disconnected: %s", charge_point_code)
    except Exception:
        logger.exception("OCPP WebSocket failed for %s", charge_point_code)
        try:
            await websocket.close(code=1011)
        except Exception:
            logger.debug("WebSocket was already closed for %s", charge_point_code)
    finally:
        manager.disconnect(charge_point_code, websocket)
        if manager.active_connections.get(charge_point_code) is None:
            with SessionLocal() as db:
                point = db.query(ChargePoint).filter_by(code=charge_point_code).first()
                if point and point.status != "offline":
                    point.status = "offline"
                    for connector in point.connectors:
                        connector.status = "unknown"
                    db.commit()
                    from app.services.ocpp_handlers import publish_charge_point_status
                    publish_charge_point_status(db, point.id)


def _normalize_parsed_message(message) -> tuple[int, str, Any, Any, Any, Any, Any]:
    """Give router dispatch a stable shape without re-parsing or coercing fields."""
    msg_type, msg_id, action, payload, error_description, error_details = message
    error_code = payload if msg_type == 4 else None
    if msg_type == 4:
        payload = None
    return msg_type, msg_id, action, payload, error_code, error_description, error_details
