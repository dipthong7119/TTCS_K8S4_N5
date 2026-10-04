"""OCPP status mapping and monitoring response serialization (T-20, T-23)."""

from datetime import UTC, datetime, timedelta

from app.config import settings

STATUS_MAPPING = {
    "Available": "rảnh",
    "Preparing": "bận",
    "Charging": "bận",
    "SuspendedEV": "bận",
    "SuspendedEVSE": "bận",
    "Finishing": "bận",
    "Reserved": "đặt chỗ",
    "Unavailable": "lỗi",
    "Faulted": "lỗi",
}


def map_status(ocpp_status: str) -> str:
    """Map known OCPP values to UI values, preserving unknown as a safe state."""
    return STATUS_MAPPING.get(ocpp_status, "unknown")


def is_charge_point_stale(
    last_seen_at: datetime | None, now: datetime | None = None
) -> bool:
    if last_seen_at is None:
        return True
    now = now or datetime.now(UTC)
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=UTC)
    timeout = (
        settings.OCPP_HEARTBEAT_INTERVAL_SECONDS * settings.OCPP_HEARTBEAT_MULTIPLIER
    )
    return last_seen_at < now - timedelta(seconds=timeout)


def station_status_payload(station, now: datetime | None = None) -> dict:
    """Build one station→charge point→connector tree, deriving stale state."""
    now = now or datetime.now(UTC)
    charge_points = []
    for point in station.charge_points:
        stale = is_charge_point_stale(point.last_seen_at, now)
        connectors = [
            {
                "id": connector.id,
                "connector_id": connector.connector_id,
                "status": "unknown"
                if stale or point.status == "offline"
                else connector.status,
                "ocpp_status": connector.ocpp_status,
                "error_code": connector.error_code,
                "updated_at": connector.updated_at.isoformat(),
            }
            for connector in sorted(
                point.connectors, key=lambda item: item.connector_id
            )
        ]
        charge_points.append(
            {
                "id": point.id,
                "code": point.code,
                "status": "offline" if stale else point.status,
                "ocpp_status": point.ocpp_status,
                "vendor": point.vendor,
                "model": point.model,
                "firmware_version": point.firmware_version,
                "last_seen_at": point.last_seen_at.isoformat()
                if point.last_seen_at
                else None,
                "connectors": connectors,
            }
        )
    return {
        "id": station.id,
        "name": station.name,
        "address": station.address,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "status": station.status,
        "charge_points": charge_points,
    }
