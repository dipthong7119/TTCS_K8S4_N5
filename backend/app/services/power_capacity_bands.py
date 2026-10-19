"""Validation and effective-limit lookup for station power bands (SCRUM-83)."""

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.models.station_power_band import StationPowerBand
from app.models.station_tariff import StationTariff

DEFAULT_STATION_TIMEZONE = "Asia/Ho_Chi_Minh"


class PowerBandOverlapError(ValueError):
    """Raised when a station power band overlaps an existing band."""


def station_power_timezone(db: Session, station_id: int) -> str:
    """Match the station revenue API's current tariff timezone fallback."""
    tariff = (
        db.query(StationTariff)
        .filter(
            StationTariff.station_id == station_id,
            StationTariff.is_demo.is_(False),
        )
        .order_by(StationTariff.effective_from.desc(), StationTariff.id.desc())
        .first()
    )
    timezone_name = tariff.timezone_name if tariff else DEFAULT_STATION_TIMEZONE
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, TypeError, ValueError):
        return DEFAULT_STATION_TIMEZONE
    return timezone_name


def _band_segments(start_minute: int, end_minute: int) -> list[tuple[int, int]]:
    if not 0 <= start_minute < 1440 or not 0 <= end_minute <= 1440:
        raise ValueError("Khung giờ không hợp lệ")
    if start_minute == end_minute:
        raise ValueError("Giờ bắt đầu và kết thúc không được trùng nhau")
    if start_minute < end_minute:
        return [(start_minute, end_minute)]
    segments = [(start_minute, 1440)]
    if end_minute:
        segments.append((0, end_minute))
    return segments


def ensure_no_power_band_overlap(
    db: Session,
    station_id: int,
    start_minute: int,
    end_minute: int,
    *,
    exclude_band_id: int | None = None,
) -> None:
    proposed_segments = _band_segments(start_minute, end_minute)
    query = db.query(StationPowerBand).filter(
        StationPowerBand.station_id == station_id
    )
    if exclude_band_id is not None:
        query = query.filter(StationPowerBand.id != exclude_band_id)

    for existing in query.all():
        existing_segments = _band_segments(
            existing.start_minute, existing.end_minute
        )
        if any(
            max(start_a, start_b) < min(end_a, end_b)
            for start_a, end_a in proposed_segments
            for start_b, end_b in existing_segments
        ):
            raise PowerBandOverlapError(
                f"Khung giờ bị chồng lấn với khung công suất #{existing.id}"
            )


def effective_station_power_limit_kw(
    db: Session,
    station_id: int,
    default_limit_kw: Decimal | None,
    at: datetime | None = None,
) -> Decimal | None:
    """Return the matching local-time limit, falling back to SCRUM-80."""
    bands = (
        db.query(StationPowerBand)
        .filter(StationPowerBand.station_id == station_id)
        .order_by(StationPowerBand.start_minute, StationPowerBand.id)
        .all()
    )
    if not bands:
        return Decimal(default_limit_kw) if default_limit_kw is not None else None

    moment = at or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    else:
        moment = moment.astimezone(UTC)
    local_time = moment.astimezone(ZoneInfo(station_power_timezone(db, station_id)))
    minute = local_time.hour * 60 + local_time.minute

    for band in bands:
        if band.start_minute < band.end_minute:
            contains_time = band.start_minute <= minute < band.end_minute
        else:
            contains_time = minute >= band.start_minute or minute < band.end_minute
        if contains_time:
            return Decimal(band.power_limit_kw)

    return Decimal(default_limit_kw) if default_limit_kw is not None else None
