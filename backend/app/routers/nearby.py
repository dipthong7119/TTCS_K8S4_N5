"""
routers/nearby.py — S-47 "Tài xế tìm trạm gần và thấy đầu nối nào đang rảnh"

Route: GET /api/stations/nearby
  - Đã đăng nhập: mọi vai trò (driver, station_owner, operator, admin).
  - Chưa đăng nhập: 401.
  - Chỉ trả trạm status == 'active'; trạm inactive/maintenance/locked KHÔNG bao giờ lộ.
  - Không trả thông tin nội bộ: owner_id, charge_point.code, error_code, firmware.

Lý do tên route '/api/stations/nearby' (không phải '/api/nearby-stations'):
  - Nhất quán với prefix '/api/stations' đã có trong main.py.
  - Không đụng route HTML '/stations' trong pages.py (HTML router không có prefix /api).
  - FastAPI khớp '/stations/nearby' trước '/{station_id}' vì path literal ưu tiên hơn parameter.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.services.nearby import find_nearby_stations

router = APIRouter(
    prefix="/stations",
    tags=["stations", "nearby"],
    dependencies=[Depends(deny_unannotated_route)],
)


@router.get(
    "/nearby",
    summary="S-47 — Tìm trạm sạc gần vị trí hoặc theo tên/địa chỉ",
    dependencies=[Depends(require_role("driver", "station_owner", "operator", "admin"))],
)
async def get_nearby_stations(
    _current_user: CurrentUser,
    db: Session = Depends(get_db),
    # Toạ độ — cùng có hoặc cùng không
    lat: float | None = Query(None, description="Vĩ độ (WGS-84), khoảng [-90, 90]"),
    lng: float | None = Query(None, description="Kinh độ (WGS-84), khoảng [-180, 180]"),
    # Bán kính tìm kiếm (km)
    radius_km: float | None = Query(
        None,
        gt=0,
        description=f"Bán kính tìm kiếm (km). Mặc định {settings.NEARBY_DEFAULT_RADIUS_KM}, "
                    f"tối đa {settings.NEARBY_MAX_RADIUS_KM}. Vượt trần → dùng trần.",
    ),
    # Tìm theo tên/địa chỉ
    q: str | None = Query(None, min_length=1, description="Từ khoá tên hoặc địa chỉ trạm"),
    # Lọc chỉ trạm còn đầu nối rảnh
    available_only: bool = Query(False, description="Chỉ trả trạm có ít nhất 1 đầu nối rảnh"),
    # Phân trang
    limit: int = Query(
        settings.NEARBY_DEFAULT_LIMIT,
        ge=1,
        le=settings.NEARBY_MAX_LIMIT,
        description=f"Số trạm tối đa trả về (tối đa {settings.NEARBY_MAX_LIMIT})",
    ),
    offset: int = Query(0, ge=0, description="Vị trí bắt đầu phân trang"),
):
    """Tìm trạm sạc đang hoạt động, kèm thông tin đầu nối rảnh.

    **Chế độ vị trí** (`lat` + `lng`):
      - Sắp theo khoảng cách tăng dần; mỗi trạm kèm `distance_km`.
      - Nếu `radius_km` vượt trần thì dùng trần (không báo lỗi).

    **Chế độ từ khoá** (chỉ `q`, không có `lat`/`lng`):
      - Tìm theo tên hoặc địa chỉ (không phân biệt hoa/thường).
      - *Giới hạn SQLite*: không tìm được theo dấu tiếng Việt
        (ví dụ: "tram" KHÔNG khớp "trạm"); PostgreSQL hỗ trợ tốt hơn qua `unaccent`.
      - Sắp theo tên A-Z.

    **Lỗi 422**:
      - Không có cả `lat/lng` lẫn `q`.
      - `lat` ngoài [-90, 90] hoặc `lng` ngoài [-180, 180].
      - Chỉ có `lat` mà không có `lng` hoặc ngược lại.
    """
    # ── Kiểm tra đầu vào ────────────────────────────────────────────────────

    # Kiểm tra toạ độ hợp lệ
    if lat is not None and (lat < -90 or lat > 90):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "lat phải nằm trong khoảng [-90, 90]", "code": "INVALID_LAT"},
        )
    if lng is not None and (lng < -180 or lng > 180):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": "lng phải nằm trong khoảng [-180, 180]", "code": "INVALID_LNG"},
        )

    # Kiểm tra cặp lat/lng — phải có cùng nhau hoặc cùng không
    has_lat = lat is not None
    has_lng = lng is not None
    if has_lat != has_lng:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "detail": "lat và lng phải được cung cấp cùng nhau hoặc không cùng nhau",
                "code": "PARTIAL_LOCATION",
            },
        )

    # Kiểm tra: phải có lat/lng hoặc q
    if not has_lat and not q:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "detail": "Phải cung cấp lat+lng hoặc q (từ khoá tìm kiếm)",
                "code": "LOCATION_OR_QUERY_REQUIRED",
            },
        )

    # ── Xử lý radius_km: vượt trần thì cắt về trần ─────────────────────────
    effective_radius = settings.NEARBY_DEFAULT_RADIUS_KM if radius_km is None else radius_km
    effective_radius = min(effective_radius, settings.NEARBY_MAX_RADIUS_KM)

    # ── Gọi service ─────────────────────────────────────────────────────────
    stations = find_nearby_stations(
        db,
        lat=lat,
        lng=lng,
        radius_km=effective_radius,
        q=q,
        available_only=available_only,
        limit=limit,
        offset=offset,
    )

    return {"items": stations, "count": len(stations), "offset": offset}
