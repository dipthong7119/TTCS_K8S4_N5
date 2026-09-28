"""Time-band charging prices using integer VND and cumulative meter readings."""

from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEMO_TARIFF_BANDS = (
    {"label": "Thấp điểm", "start_minute": 0, "end_minute": 360, "price_vnd_per_kwh": 3000},
    {"label": "Tiêu chuẩn", "start_minute": 360, "end_minute": 1020, "price_vnd_per_kwh": 4000},
    {"label": "Cao điểm", "start_minute": 1020, "end_minute": 1320, "price_vnd_per_kwh": 5000},
    {"label": "Thấp điểm", "start_minute": 1320, "end_minute": 1440, "price_vnd_per_kwh": 3000},
)
DEMO_TARIFF_TIMEZONE = "Asia/Ho_Chi_Minh"
CALCULATION_VERSION = "time-band-v1"


def validate_daily_bands(bands) -> None:
    """Reject gaps, overlaps, invalid rates, or a schedule that misses 24:00."""
    ordered = sorted(bands, key=lambda band: _band_value(band, "start_minute"))
    cursor = 0
    if not ordered:
        raise ValueError("Biểu giá phải có ít nhất một khung giờ")
    for band in ordered:
        start = int(_band_value(band, "start_minute"))
        end = int(_band_value(band, "end_minute"))
        price = int(_band_value(band, "price_vnd_per_kwh"))
        if start != cursor:
            raise ValueError("Các khung giá phải liền nhau, không chồng lấn và phủ đủ 24 giờ")
        if not 0 <= start < end <= 1440 or price < 0:
            raise ValueError("Khung giờ hoặc đơn giá không hợp lệ")
        cursor = end
    if cursor != 1440:
        raise ValueError("Biểu giá phải kết thúc lúc 24:00")


def calculate_session_price(
    *,
    started_at: datetime,
    ended_at: datetime,
    meter_start_wh: int,
    meter_stop_wh: int,
    meter_readings: list[dict],
    bands,
    timezone_name: str,
) -> dict:
    """Split meter energy by local price bands; round each invoice segment once."""
    validate_daily_bands(bands)
    if meter_stop_wh < meter_start_wh:
        raise ValueError("Số đo cuối nhỏ hơn số đo đầu")

    try:
        station_zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, TypeError) as exc:
        raise ValueError("Múi giờ trạm không hợp lệ") from exc

    start_utc = _as_utc(started_at)
    end_utc = _as_utc(ended_at)
    if end_utc < start_utc:
        raise ValueError("Thời điểm kết thúc trước thời điểm bắt đầu")
    if end_utc == start_utc:
        return {"total_vnd": 0, "segments": []}

    points = [(start_utc, Decimal(meter_start_wh))]
    for reading in meter_readings:
        if reading.get("measurand", "Energy.Active.Import.Register") != "Energy.Active.Import.Register":
            continue
        timestamp = _reading_time(reading.get("measured_at"))
        value_wh = _reading_wh(reading.get("value"), reading.get("unit"))
        if timestamp is None or value_wh is None or not start_utc < timestamp < end_utc:
            continue
        if Decimal(meter_start_wh) <= value_wh <= Decimal(meter_stop_wh):
            points.append((timestamp, value_wh))
    points.append((end_utc, Decimal(meter_stop_wh)))
    points.sort(key=lambda item: (item[0], item[1]))

    # At the same instant retain the highest cumulative register value.
    distinct_points = []
    for point in points:
        if distinct_points and distinct_points[-1][0] == point[0]:
            distinct_points[-1] = point
        else:
            distinct_points.append(point)

    monotonic_points = [distinct_points[0]]
    for point in distinct_points[1:]:
        if point[1] >= monotonic_points[-1][1]:
            monotonic_points.append(point)
    if monotonic_points[-1][0] != end_utc or monotonic_points[-1][1] != Decimal(meter_stop_wh):
        raise ValueError("Số đo tích lũy không tăng hợp lệ tới thời điểm kết thúc")

    ordered_bands = sorted(bands, key=lambda band: _band_value(band, "start_minute"))
    boundary_minutes = {0, 1440}
    for band in ordered_bands:
        boundary_minutes.add(int(_band_value(band, "start_minute")))
        boundary_minutes.add(int(_band_value(band, "end_minute")))

    grouped_segments = {}
    for (interval_start, wh_start), (interval_end, wh_end) in zip(
        monotonic_points, monotonic_points[1:]
    ):
        duration_seconds = Decimal(str((interval_end - interval_start).total_seconds()))
        if duration_seconds <= 0 or wh_end < wh_start:
            continue
        cuts = [interval_start, *_tariff_boundaries(interval_start, interval_end, station_zone, boundary_minutes), interval_end]
        for segment_start, segment_end in zip(cuts, cuts[1:]):
            band = _band_at(segment_start, station_zone, ordered_bands)
            seconds = Decimal(str((segment_end - segment_start).total_seconds()))
            energy_wh = (wh_end - wh_start) * seconds / duration_seconds
            price = int(_band_value(band, "price_vnd_per_kwh"))
            window_start, window_end = _band_window(segment_start, band, station_zone)
            key = (window_start, window_end, str(_band_value(band, "label")), price)
            current = grouped_segments.setdefault(
                key,
                {"start": segment_start, "end": segment_end, "energy_wh": Decimal(0)},
            )
            current["start"] = min(current["start"], segment_start)
            current["end"] = max(current["end"], segment_end)
            current["energy_wh"] += energy_wh

    segments = []
    for (window_start, _window_end, label, price), item in sorted(
        grouped_segments.items(), key=lambda pair: pair[1]["start"]
    ):
        energy_wh = item["energy_wh"]
        amount_vnd = int(
            (energy_wh * Decimal(price) / Decimal(1000)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        segments.append(
            {
                "from": item["start"].astimezone(station_zone).isoformat(),
                "to": item["end"].astimezone(station_zone).isoformat(),
                "band": label,
                "energy_kwh": format((energy_wh / Decimal(1000)).quantize(Decimal("0.000001")), "f"),
                "price_vnd_per_kwh": price,
                "amount_vnd": amount_vnd,
            }
        )

    return {"total_vnd": sum(segment["amount_vnd"] for segment in segments), "segments": segments}


def _band_value(band, key):
    return band[key] if isinstance(band, dict) else getattr(band, key)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _reading_time(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _reading_wh(value, unit) -> Decimal | None:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    normalized_unit = (unit or "Wh").strip().lower()
    if normalized_unit == "kwh":
        return amount * Decimal(1000)
    if normalized_unit == "wh":
        return amount
    return None


def _tariff_boundaries(start, end, station_zone, boundary_minutes):
    local_start = start.astimezone(station_zone)
    local_end = end.astimezone(station_zone)
    day = local_start.date()
    boundaries = []
    while day <= local_end.date():
        for minute in boundary_minutes:
            if minute == 1440:
                boundary_day = date.fromordinal(day.toordinal() + 1)
                hour, minute_part = 0, 0
            else:
                boundary_day = day
                hour, minute_part = divmod(minute, 60)
            local_boundary = datetime.combine(
                boundary_day, time(hour, minute_part), tzinfo=station_zone
            )
            boundary = local_boundary.astimezone(timezone.utc)
            if start < boundary < end:
                boundaries.append(boundary)
        day = date.fromordinal(day.toordinal() + 1)
    return sorted(set(boundaries))


def _band_at(segment_start, station_zone, bands):
    local_time = segment_start.astimezone(station_zone)
    minute = local_time.hour * 60 + local_time.minute
    for band in bands:
        start = int(_band_value(band, "start_minute"))
        end = int(_band_value(band, "end_minute"))
        if start <= minute < end:
            return band
    raise ValueError("Không tìm thấy đơn giá cho một đoạn thời gian")


def _band_window(segment_start, band, station_zone):
    local_start = segment_start.astimezone(station_zone)
    band_start = int(_band_value(band, "start_minute"))
    band_end = int(_band_value(band, "end_minute"))
    start_hour, start_minute = divmod(band_start, 60)
    end_hour, end_minute = (0, 0) if band_end == 1440 else divmod(band_end, 60)
    start_local = datetime.combine(
        local_start.date(), time(start_hour, start_minute), tzinfo=station_zone
    )
    end_date = date.fromordinal(local_start.date().toordinal() + 1) if band_end == 1440 else local_start.date()
    end_local = datetime.combine(end_date, time(end_hour, end_minute), tzinfo=station_zone)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
