"""Idempotent OCPP background maintenance jobs (T-26, T-31)."""

import asyncio
import logging

from sqlalchemy import func, text
from sqlalchemy.orm import joinedload

from app.config import settings
from app.database import SessionLocal
from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.services.ocpp_status import station_status_payload

logger = logging.getLogger(__name__)


def _stale_cutoff(db):
    timeout = settings.OCPP_HEARTBEAT_INTERVAL_SECONDS * settings.OCPP_HEARTBEAT_MULTIPLIER
    if db.get_bind().dialect.name == "sqlite":
        return func.datetime(func.current_timestamp(), f"-{timeout} seconds")
    return func.current_timestamp() - text(f"INTERVAL '{timeout} seconds'")


def expire_stale_charge_points_once(db) -> int:
    """Persist stale state and clear connector status; repeated runs are no-ops."""
    stale_points = (
        db.query(ChargePoint)
        .filter(
            ChargePoint.status == "online",
            (ChargePoint.last_seen_at.is_(None)) | (ChargePoint.last_seen_at < _stale_cutoff(db)),
        )
        .all()
    )
    if not stale_points:
        return 0

    station_ids = {point.station_id for point in stale_points}
    for point in stale_points:
        point.status = "offline"
        for connector in point.connectors:
            connector.status = "unknown"
        logger.info("Charge point marked offline after missed heartbeats: %s", point.code)
    db.commit()

    from app.routers.monitoring import notify_status_change

    stations = (
        db.query(Station)
        .options(joinedload(Station.charge_points).joinedload(ChargePoint.connectors))
        .filter(Station.id.in_(station_ids))
        .all()
    )
    for station in stations:
        snapshot = station_status_payload(station)
        notify_status_change(station.id, snapshot["charge_points"], station.owner_id)
    return len(stale_points)


async def check_offline_charge_points():
    while True:
        try:
            with SessionLocal() as db:
                expire_stale_charge_points_once(db)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Offline charge point check failed")
        await asyncio.sleep(settings.OCPP_JOB_POLL_SECONDS)


def cleanup_old_ocpp_messages_once(db) -> int:
    from app.models.ocpp_message import OcppMessage

    retention = settings.OCPP_MESSAGE_RETENTION_DAYS
    if db.get_bind().dialect.name == "sqlite":
        cutoff = func.datetime(func.current_timestamp(), f"-{retention} days")
    else:
        cutoff = func.current_timestamp() - text(f"INTERVAL '{retention} days'")
    deleted = (
        db.query(OcppMessage)
        .filter(OcppMessage.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


async def cleanup_old_ocpp_messages():
    while True:
        try:
            with SessionLocal() as db:
                deleted = cleanup_old_ocpp_messages_once(db)
                if deleted:
                    logger.info("Removed %s expired OCPP idempotency records", deleted)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("OCPP message cleanup failed")
        await asyncio.sleep(3600)
