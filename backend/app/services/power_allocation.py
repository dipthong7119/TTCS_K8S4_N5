"""Equal-share charging power allocation and OCPP profile dispatch."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_session import ChargingSession
from app.models.station import Station
from app.services.power_profiles import (
    PowerAllocationTarget,
    dispatch_power_profile,
    record_profile_outcome,
    record_profile_request,
    send_power_profile,
    stop_rejected_session,
)

logger = logging.getLogger(__name__)
REBALANCE_COALESCE_SECONDS = 5
NON_CHARGING_STATES = {
    "Available", "Preparing", "SuspendedEV", "SuspendedEVSE", "Finishing",
    "Reserved", "Unavailable", "Faulted",
}


@dataclass
class _RebalanceState:
    version: int = 0
    task: asyncio.Task | None = None


_rebalance_states: dict[int, _RebalanceState] = {}
_rebalance_locks: dict[int, asyncio.Lock] = {}


def calculate_equal_share_limits(
    station_limit_kw: Decimal,
    participants: list[tuple[int, Decimal]],
) -> dict[int, int]:
    """Return a safe equal share in whole watts, capped by each connector rating."""
    if not participants:
        return {}
    station_limit_w = _kw_to_watts(station_limit_kw)
    equal_share_w = station_limit_w // len(participants)
    return {
        session_id: min(equal_share_w, _kw_to_watts(rated_power_kw))
        for session_id, rated_power_kw in participants
    }


def _kw_to_watts(value: Decimal) -> int:
    return int((Decimal(value) * 1000).to_integral_value(rounding=ROUND_FLOOR))


def schedule_station_rebalance(station_id: int) -> None:
    """Coalesce station events for five seconds, then allocate from current state."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("Power rebalance requires the application event loop: station=%s", station_id)
        return

    state = _rebalance_states.setdefault(station_id, _RebalanceState())
    state.version += 1
    if state.task is None or state.task.done():
        state.task = loop.create_task(_run_station_rebalance(station_id, state))


async def _run_station_rebalance(station_id: int, state: _RebalanceState) -> None:
    try:
        while True:
            await asyncio.sleep(REBALANCE_COALESCE_SECONDS)
            event_version = state.version
            lock = _rebalance_locks.setdefault(station_id, asyncio.Lock())
            async with lock:
                with SessionLocal() as db:
                    await rebalance_station_once(db, station_id)
            if state.version == event_version:
                return
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Station power rebalance failed: station_id=%s", station_id)
    finally:
        state.task = None


async def rebalance_station_once(
    db: Session,
    station_id: int,
    *,
    send_call: Callable[..., Awaitable[dict]] | None = None,
) -> int:
    """Persist changed equal-share limits and send/log OCPP profiles for them."""
    station = (
        db.query(Station)
        .filter(Station.id == station_id)
        .with_for_update()
        .first()
    )
    if station is None or station.power_limit_kw is None:
        return 0

    rows = (
        db.query(ChargingSession, Connector, ChargePoint)
        .join(
            Connector,
            and_(
                Connector.charge_point_id == ChargingSession.charge_point_id,
                Connector.connector_id == ChargingSession.connector_number,
            ),
        )
        .join(ChargePoint, ChargePoint.id == ChargingSession.charge_point_id)
        .filter(
            ChargingSession.station_id == station.id,
            ChargingSession.ended_at.is_(None),
            ChargingSession.status == "active",
        )
        .order_by(ChargingSession.id)
        .with_for_update()
        .all()
    )
    participants = [
        (session, connector, point)
        for session, connector, point in rows
        if connector.ocpp_status not in NON_CHARGING_STATES
    ]
    if not participants:
        db.commit()
        return 0

    missing_ratings = [
        session.id for session, connector, _point in participants
        if connector.rated_power_kw is None
    ]
    if missing_ratings:
        logger.warning(
            "Power allocation skipped because connector ratings are missing: station_id=%s sessions=%s",
            station.id,
            missing_ratings,
        )
        db.rollback()
        return 0

    limits = calculate_equal_share_limits(
        Decimal(station.power_limit_kw),
        [(session.id, Decimal(connector.rated_power_kw)) for session, connector, _ in participants],
    )
    nominal_kw = sum(
        (Decimal(connector.rated_power_kw) for _, connector, _ in participants),
        Decimal(0),
    )
    if nominal_kw > Decimal(station.power_limit_kw):
        logger.warning(
            "Active connector ratings exceed station limit: station_id=%s nominal_kw=%s limit_kw=%s",
            station.id,
            nominal_kw,
            station.power_limit_kw,
        )

    changed: list[PowerAllocationTarget] = []
    for session, connector, point in participants:
        limit_w = limits[session.id]
        previous_limit_w = session.requested_power_limit_w
        if previous_limit_w is None:
            previous_limit_w = _kw_to_watts(Decimal(connector.rated_power_kw))
        if previous_limit_w == limit_w:
            continue
        target = PowerAllocationTarget(
            session_id=session.id,
            charge_point_code=point.code,
            connector_number=connector.connector_id,
            limit_w=limit_w,
        )
        changed.append(target)
        record_profile_request(db, target)
        session.requested_power_limit_w = limit_w
    db.commit()
    if not changed:
        return 0

    if send_call is None:
        for target in changed:
            asyncio.create_task(dispatch_power_profile(target))
        await asyncio.sleep(0)
    else:
        results = await asyncio.gather(
            *(send_power_profile(target, send_call) for target in changed)
        )
        for target, outcome in zip(changed, results, strict=True):
            is_current = record_profile_outcome(db, target, outcome)
            if outcome == "Rejected" and is_current:
                await stop_rejected_session(db, target, send_call)
    return len(changed)
