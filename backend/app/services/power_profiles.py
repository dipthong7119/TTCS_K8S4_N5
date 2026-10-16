"""OCPP charging profile requests and rejection handling."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.charging_session import ChargingSession
from app.services.audit import append_audit
from app.services.connection_manager import manager
from app.services.ocpp_parser import OCPPError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PowerAllocationTarget:
    session_id: int
    charge_point_code: str
    connector_number: int
    limit_w: int


def _profile_payload(target: PowerAllocationTarget) -> dict:
    return {
        "connectorId": target.connector_number,
        "csChargingProfiles": {
            "chargingProfileId": target.session_id,
            "stackLevel": 0,
            "chargingProfilePurpose": "TxProfile",
            "chargingProfileKind": "Absolute",
            "transactionId": target.session_id,
            "chargingSchedule": {
                "chargingRateUnit": "W",
                "chargingSchedulePeriod": [{"startPeriod": 0, "limit": target.limit_w}],
            },
        },
    }


def record_profile_request(db: Session, target: PowerAllocationTarget) -> None:
    append_audit(
        db,
        action="charging_power.profile_requested",
        object_type="charging_session",
        object_id=target.session_id,
        charge_point_code=target.charge_point_code,
        details={
            "command": "SetChargingProfile",
            "connector_id": target.connector_number,
            "limit_w": target.limit_w,
            "outcome": "queued",
            "verification": "command_log_r08",
        },
    )


async def send_power_profile(
    target: PowerAllocationTarget,
    send_call: Callable[..., Awaitable[dict]],
) -> str:
    payload = _profile_payload(target)
    logger.info(
        "SetChargingProfile requested: session=%s charge_point=%s connector=%s limit_w=%s",
        target.session_id,
        target.charge_point_code,
        target.connector_number,
        target.limit_w,
    )
    try:
        result = await send_call(target.charge_point_code, "SetChargingProfile", payload)
    except asyncio.TimeoutError:
        # R-08 accepts the command log when the project simulator has no profile handler.
        logger.warning("SetChargingProfile timed out; command recorded per R-08: session=%s", target.session_id)
        return "no_reply_logged_r08"
    except ConnectionError:
        logger.warning("SetChargingProfile could not reach charge point: session=%s", target.session_id)
        return "disconnected"
    except OCPPError:
        logger.exception("SetChargingProfile returned CALLERROR: session=%s", target.session_id)
        return "call_error"
    status = result.get("status") if isinstance(result, dict) else None
    if status in {"Accepted", "Rejected"}:
        return status
    return "unknown_response"


def record_profile_outcome(
    db: Session, target: PowerAllocationTarget, outcome: str
) -> bool:
    session = db.query(ChargingSession).filter_by(id=target.session_id).first()
    is_current = (
        session is not None
        and session.ended_at is None
        and session.requested_power_limit_w == target.limit_w
    )
    if is_current and outcome == "disconnected":
        session.requested_power_limit_w = None
    append_audit(
        db,
        action="charging_power.profile_result",
        object_type="charging_session",
        object_id=target.session_id,
        charge_point_code=target.charge_point_code,
        details={
            "command": "SetChargingProfile",
            "connector_id": target.connector_number,
            "limit_w": target.limit_w,
            "outcome": outcome,
            "verification": "command_log_r08",
        },
    )
    db.commit()
    if outcome == "Rejected":
        logger.error(
            "Charge point rejected power limit; requesting session stop: session=%s cp=%s connector=%s",
            target.session_id,
            target.charge_point_code,
            target.connector_number,
        )
    return is_current


async def dispatch_power_profile(target: PowerAllocationTarget) -> None:
    """Send asynchronously so a missing CALLRESULT cannot delay later reallocations."""
    try:
        outcome = await send_power_profile(target, manager.send_call)
        with SessionLocal() as db:
            is_current = record_profile_outcome(db, target, outcome)
            if outcome == "Rejected" and is_current:
                await stop_rejected_session(db, target, manager.send_call)
    except Exception:
        logger.exception(
            "Power profile dispatch failed: session=%s charge_point=%s",
            target.session_id,
            target.charge_point_code,
        )


async def stop_rejected_session(
    db: Session,
    target: PowerAllocationTarget,
    send_call: Callable[..., Awaitable[dict]],
) -> None:
    session = (
        db.query(ChargingSession)
        .filter(
            ChargingSession.id == target.session_id,
            ChargingSession.ended_at.is_(None),
        )
        .first()
    )
    if session is None:
        return
    try:
        result = await send_call(
            target.charge_point_code,
            "RemoteStopTransaction",
            {"transactionId": target.session_id},
        )
        outcome = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
    except asyncio.TimeoutError:
        outcome = "timeout"
    except (ConnectionError, OCPPError):
        outcome = "call_error"

    if outcome == "Accepted":
        session.remote_stop_requested_at = datetime.now(UTC).replace(tzinfo=None)
    append_audit(
        db,
        action="charging_power.rejected_session_stop",
        object_type="charging_session",
        object_id=target.session_id,
        charge_point_code=target.charge_point_code,
        details={
            "command": "RemoteStopTransaction",
            "outcome": outcome,
            "reason": "SetChargingProfile_rejected",
        },
    )
    db.commit()
    if outcome != "Accepted":
        logger.error(
            "Unable to stop session after profile rejection: session=%s outcome=%s",
            target.session_id,
            outcome,
        )
