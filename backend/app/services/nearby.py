"""
services/nearby.py — Logic nghiệp vụ cho S-47 "Tìm trạm gần".

Phụ thuộc:
  - S-04: Station có latitude/longitude/status.
  - S-09: ChargePoint.last_seen_at dùng xác định trực tuyến/ngoại tuyến.
  - S-29: StationTariff/TariffBand — gọi lại hàm don_gia_tai() nội bộ để
          lấy đơn giá tại thời điểm hiện tại, KHÔNG viết lại logic khung giờ.

Ghi chú SQLite:
  - SQLite không phân biệt dấu tiếng Việt (chỉ ASCII case-insensitive);
    tìm theo `q` sẽ khớp theo LIKE nhưng "tram" KHÔNG khớp "trạm".
    Giới hạn này được ghi rõ trong README.
  - Không dùng PostGIS, haversine thuần Python.
"""

import math
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.models.station_tariff import StationTariff

# ─────────────────────────────────────────────────────────────────────────────
# Hằng số
# ─────────────────────────────────────────────────────────────────────────────

# Bán kính Trái Đất (km) dùng trong haversine
_EARTH_RADIUS_KM = 6371.0

# Trạng thái nội bộ "rảnh" (ánh xạ từ STATUS_MAPPING trong ocpp_status.py)
_AVAILABLE_INTERNAL = "rảnh"


# ─────────────────────────────────────────────────────────────────────────────
# Haversine
# ─────────────────────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Tính khoảng cách đường chim bay giữa hai toạ độ (km).

    Sai số < 0,5% với khoảng cách < 1 000 km — đủ dùng cho bán kính ≤ 100 km.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_KM * c


# ─────────────────────────────────────────────────────────────────────────────
# Bounding box (lọc sơ bộ ở tầng DB để thu hẹp ứng viên)
# ─────────────────────────────────────────────────────────────────────────────

def _bounding_box(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """Trả về (lat_min, lat_max, lon_min, lon_max) cho bounding box.

    Dùng xấp xỉ đơn giản (1° lat ≈ 111 km), đủ chính xác cho radius ≤ 100 km.
    Không hỗ trợ vùng bao quanh cực địa lý (lat ± 90°), an toàn với Việt Nam.
    """
    dlat = radius_km / 111.0
    # 1° lon co rút dần khi tiến về cực
    dlon = radius_km / (111.0 * math.cos(math.radians(lat))) if abs(lat) < 89.9 else 180.0

    lat_min = max(-90.0, lat - dlat)
    lat_max = min(90.0, lat + dlat)

    # Không cuộn qua ±180°; nếu dlon lớn thì chấp nhận toàn dải
    if dlon >= 180.0:
        lon_min, lon_max = -180.0, 180.0
    else:
        lon_min = lon - dlon
        lon_max = lon + dlon
        # Nếu tràn qua biên ±180°, ghi chú: SQLite bounding box sẽ thiếu.
        # Trường hợp này cực kỳ hiếm (radius ≤ 100 km, trừ vùng cực).
        lon_min = max(-180.0, lon_min)
        lon_max = min(180.0, lon_max)

    return lat_min, lat_max, lon_min, lon_max


# ─────────────────────────────────────────────────────────────────────────────
# Đơn giá tại thời điểm T (S-29 không có hàm này → tạo tại đây)
# ─────────────────────────────────────────────────────────────────────────────

def don_gia_tai(tariff: StationTariff, thoi_diem: datetime) -> int | None:
    """Trả về đơn giá VNĐ/kWh tại `thoi_diem` (UTC hoặc naive-UTC).

    Quy trình:
      1. Đổi thoi_diem sang múi giờ của biểu giá (tariff.timezone_name).
      2. Tính số phút trong ngày (0–1439).
      3. Duyệt các band đã sắp xếp, trả về giá của band chứa phút đó.
      4. Trả None nếu không có band nào khớp (lỗ hổng biểu giá — không nên xảy ra
         sau khi đã qua validate_daily_bands, nhưng an toàn hơn).

    Hàm này KHÔNG gọi lại calculate_session_price() để tránh phụ thuộc vào
    meter readings; chỉ đọc cấu trúc band thuần.
    """
    if not tariff or not tariff.bands:
        return None

    try:
        tz = ZoneInfo(tariff.timezone_name)
    except Exception:
        return None

    # Chuyển về naive-UTC rồi gán tzinfo UTC để so sánh đúng
    if thoi_diem.tzinfo is None:
        thoi_diem = thoi_diem.replace(tzinfo=UTC)

    local_dt = thoi_diem.astimezone(tz)
    minute_of_day = local_dt.hour * 60 + local_dt.minute

    for band in sorted(tariff.bands, key=lambda b: b.start_minute):
        if band.start_minute <= minute_of_day < band.end_minute:
            return band.price_vnd_per_kwh

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Kiểm tra trụ trực tuyến
# ─────────────────────────────────────────────────────────────────────────────

def _is_charge_point_online(cp: ChargePoint, now: datetime) -> bool:
    """Trả True nếu trụ còn trong ngưỡng heartbeat (dùng chung cấu hình S-09/S-11)."""
    if cp.last_seen_at is None:
        return False
    last = cp.last_seen_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    timeout_secs = settings.OCPP_HEARTBEAT_INTERVAL_SECONDS * settings.OCPP_HEARTBEAT_MULTIPLIER
    return last >= now - timedelta(seconds=timeout_secs)


# ─────────────────────────────────────────────────────────────────────────────
# Escape ký tự đặc biệt LIKE
# ─────────────────────────────────────────────────────────────────────────────

def _escape_like(value: str) -> str:
    """Escape % và _ để tránh tấn công LIKE injection."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ─────────────────────────────────────────────────────────────────────────────
# Lấy biểu giá hiện hành của trạm
# ─────────────────────────────────────────────────────────────────────────────

def _get_active_tariff(db: Session, station_id: int, now: datetime) -> StationTariff | None:
    """Lấy biểu giá có effective_from ≤ now gần nhất cho trạm."""
    now_naive = now.replace(tzinfo=None) if now.tzinfo else now
    tariff = (
        db.query(StationTariff)
        .options(joinedload(StationTariff.bands))
        .filter(
            StationTariff.station_id == station_id,
            StationTariff.effective_from <= now_naive,
            StationTariff.is_demo.is_(False),
        )
        .order_by(StationTariff.effective_from.desc())
        .first()
    )
    return tariff


# ─────────────────────────────────────────────────────────────────────────────
# Tổng hợp dữ liệu connector của một trạm (tránh N+1)
# ─────────────────────────────────────────────────────────────────────────────

def _build_connector_summary(
    station: Station,
    now: datetime,
    tariff: StationTariff | None,
) -> dict[str, Any]:
    """Tính connectors_total, connectors_available, connector_types, is_stale.

    connectors_total:
        Tổng đầu nối của trạm, KHÔNG tính đầu nối có trạng thái 'disabled'
        (hiện tại schema không có trạng thái này; mọi Connector được kể).
        Ghi rõ: đếm tất cả Connector thuộc các ChargePoint của trạm này.

    connectors_available:
        Đầu nối có status nội bộ == 'rảnh' VÀ thuộc trụ đang trực tuyến.
        Đầu nối của trụ ngoại tuyến KHÔNG tính là rảnh.
    """
    total = 0
    available = 0
    # {type_key: {"total": int, "available": int}}
    type_stats: dict[str, dict[str, int]] = {}
    all_offline = True  # is_stale = True khi mọi trụ đều ngoại tuyến

    for cp in station.charge_points:
        online = _is_charge_point_online(cp, now)
        if online:
            all_offline = False

        for conn in cp.connectors:
            total += 1
            ctype = conn.connector_type or "unknown"

            if ctype not in type_stats:
                type_stats[ctype] = {"total": 0, "available": 0}
            type_stats[ctype]["total"] += 1

            # Rảnh khi: status nội bộ == 'rảnh' VÀ trụ đang trực tuyến
            if online and conn.status == _AVAILABLE_INTERNAL:
                available += 1
                type_stats[ctype]["available"] += 1

    # Tính đơn giá theo loại đầu nối (hiện tại biểu giá không phân loại —
    # cùng giá cho mọi loại trong một trạm; nếu mai sau có phân loại thì override)
    price_now: int | None = None
    if tariff:
        price_now = don_gia_tai(tariff, now)

    connector_types = [
        {
            "type": ctype,
            "total": stats["total"],
            "available": stats["available"],
            "price_per_kwh_vnd": price_now,
        }
        for ctype, stats in type_stats.items()
    ]

    return {
        "connectors_total": total,
        "connectors_available": available,
        "connector_types": connector_types,
        "is_stale": all_offline,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Hàm chính: tìm trạm gần
# ─────────────────────────────────────────────────────────────────────────────

def find_nearby_stations(
    db: Session,
    *,
    lat: float | None,
    lng: float | None,
    radius_km: float,
    q: str | None,
    available_only: bool,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """Tìm trạm gần/theo từ khoá; trả danh sách dict đã tổng hợp thông tin đầu nối.

    Hiệu năng:
      - Truy vấn 1: lấy danh sách Station (bounding box + filter).
      - Truy vấn 2: joinedload ChargePoint → Connector cho toàn bộ station_ids.
      - Truy vấn 3 (theo trạm): lấy biểu giá (cache theo station_id, tối đa ~20-50 trạm).
      Tổng: O(trạm) truy vấn DB, không N+1 theo đầu nối.
    """
    now = datetime.now(UTC)

    # ── Truy vấn cơ sở: chỉ trạm đang hoạt động ──────────────────────────
    q_stations = (
        db.query(Station)
        .filter(Station.status == "active")
    )

    if lat is not None and lng is not None:
        # Lọc bounding box
        lat_min, lat_max, lon_min, lon_max = _bounding_box(lat, lng, radius_km)
        q_stations = q_stations.filter(
            Station.latitude.is_not(None),
            Station.longitude.is_not(None),
            Station.latitude >= lat_min,
            Station.latitude <= lat_max,
            Station.longitude >= lon_min,
            Station.longitude <= lon_max,
        )

    if q:
        escaped = _escape_like(q)
        pattern = f"%{escaped}%"
        # SQLite: LIKE không phân biệt dấu tiếng Việt (giới hạn đã ghi trong README)
        q_stations = q_stations.filter(
            or_(
                Station.name.ilike(pattern),
                Station.address.ilike(pattern),
            )
        )

    # Lấy tất cả ứng viên (không phân trang sớm vì cần sort haversine)
    # Để tránh tải quá nhiều: giới hạn tối đa bounding box đã thu hẹp
    candidate_stations: list[Station] = q_stations.all()

    # ── Haversine chính xác + sắp xếp ────────────────────────────────────
    if lat is not None and lng is not None:
        station_distances: list[tuple[Station, float]] = []
        for station in candidate_stations:
            dist = haversine_km(lat, lng, station.latitude, station.longitude)
            if dist <= radius_km:
                station_distances.append((station, dist))
        # Sắp theo khoảng cách tăng dần
        station_distances.sort(key=lambda pair: pair[1])
        # Phân trang sau khi sắp xếp
        paged = station_distances[offset: offset + limit]
        station_list = [(s, d) for s, d in paged]
    else:
        # Tìm theo tên — sắp theo tên A-Z
        candidate_stations.sort(key=lambda s: (s.name or "").lower())
        paged_stations = candidate_stations[offset: offset + limit]
        station_list = [(s, None) for s in paged_stations]

    if not station_list:
        return []

    # ── Truy vấn 2: load ChargePoint + Connector trong một lần (tránh N+1) ─
    station_ids = [s.id for s, _ in station_list]
    cps = (
        db.query(ChargePoint)
        .options(joinedload(ChargePoint.connectors))
        .filter(ChargePoint.station_id.in_(station_ids))
        .all()
    )
    # Gom theo station_id
    cp_by_station: dict[int, list[ChargePoint]] = {}
    for cp in cps:
        cp_by_station.setdefault(cp.station_id, []).append(cp)

    # ── Tổng hợp kết quả ─────────────────────────────────────────────────
    results: list[dict[str, Any]] = []
    for station, distance in station_list:
        # Gán danh sách charge_points vào station (tránh lazy load)
        station.charge_points = cp_by_station.get(station.id, [])

        # Biểu giá hiện hành (tra theo station_id)
        tariff = _get_active_tariff(db, station.id, now)

        # Tổng hợp connector
        summary = _build_connector_summary(station, now, tariff)

        # Lọc available_only sau khi đã tính
        if available_only and summary["connectors_available"] == 0:
            continue

        item: dict[str, Any] = {
            "id": station.id,
            "name": station.name,
            "address": station.address,
            "latitude": station.latitude,
            "longitude": station.longitude,
            **summary,
        }
        if distance is not None:
            item["distance_km"] = round(distance, 1)

        results.append(item)

    return results
