"""
routers/stations.py -- CRUD trạm sạc (S-04, T-09)
Tham chieu: SPRINT_1.md T-08, T-09, SSD-1, 02_CODING_STANDARDS.md
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.station import Station
from app.models.station_tariff import StationTariff, TariffBand
from app.schemas.station import (
    StationCreate,
    StationDirectoryResponse,
    StationResponse,
    StationUpdate,
)
from app.schemas.station_tariff import StationTariffCreate, StationTariffResponse
from app.services.ownership import filter_by_owner, get_station_for_user

router = APIRouter(prefix="/stations", tags=["stations"], dependencies=[Depends(deny_unannotated_route)])


def _tariff_payload(tariff: StationTariff) -> dict:
    flat_rate = next(
        (band.price_vnd_per_kwh for band in tariff.bands
         if band.start_minute == 0 and band.end_minute == 1440),
        None,
    )
    return {
        "id": tariff.id,
        "station_id": tariff.station_id,
        "name": tariff.name,
        "timezone_name": tariff.timezone_name,
        # Database timestamps are stored as naive UTC; expose UTC explicitly.
        "effective_from": tariff.effective_from.replace(tzinfo=UTC),
        "occupancy_fee_vnd_per_minute": tariff.occupancy_fee_vnd_per_minute,
        "grace_period_minutes": tariff.grace_period_minutes,
        "is_demo": tariff.is_demo,
        "price_vnd_per_kwh": flat_rate,
    }


@router.get(
    "/{station_id}/tariffs",
    response_model=list[StationTariffResponse],
    dependencies=[Depends(require_role("station_owner", "admin"))],
)
async def list_station_tariffs(
    station_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    roles = [role.name for role in current_user.roles]
    get_station_for_user(db, station_id, current_user.id, roles, "view_tariffs")
    tariffs = (
        db.query(StationTariff)
        .filter(StationTariff.station_id == station_id)
        .options(joinedload(StationTariff.bands))
        .order_by(StationTariff.effective_from.desc(), StationTariff.id.desc())
        .all()
    )
    return [_tariff_payload(tariff) for tariff in tariffs]


@router.post(
    "/{station_id}/tariffs",
    response_model=StationTariffResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("station_owner", "admin"))],
)
async def create_station_tariff(
    station_id: int,
    body: StationTariffCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    roles = [role.name for role in current_user.roles]
    station = get_station_for_user(db, station_id, current_user.id, roles, "create_tariff")
    if "admin" not in roles and station.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Không có quyền sửa biểu giá trạm này")
    tariff_name = body.name.strip()
    if not tariff_name:
        raise HTTPException(status_code=422, detail="Tên biểu giá không được để trống")
    try:
        ZoneInfo(body.timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=422, detail="Múi giờ trạm không hợp lệ") from None

    if body.effective_from is None:
        effective_from = datetime.now(UTC).replace(tzinfo=None)
    else:
        try:
            effective_from = _normalize_effective_from(body.effective_from, body.timezone_name)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        if effective_from < datetime.now(UTC).replace(tzinfo=None):
            raise HTTPException(status_code=422, detail="Thời điểm hiệu lực không được nằm trong quá khứ")
    tariff = StationTariff(
        station_id=station.id,
        name=tariff_name,
        timezone_name=body.timezone_name,
        effective_from=effective_from,
        occupancy_fee_vnd_per_minute=body.occupancy_fee_vnd_per_minute,
        grace_period_minutes=body.grace_period_minutes,
        is_demo=False,
    )
    db.add(tariff)
    db.add(
        TariffBand(
            tariff=tariff,
            label="Cả ngày",
            start_minute=0,
            end_minute=1440,
            price_vnd_per_kwh=body.price_vnd_per_kwh,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Đã có biểu giá của trạm vào thời điểm hiệu lực này",
        ) from None
    db.refresh(tariff)
    return _tariff_payload(tariff)


def _normalize_effective_from(value: datetime | None, timezone_name: str) -> datetime:
    """Normalize API timestamps to naive UTC for database storage.

    Naive values from datetime-local are interpreted as station wall time.
    Aware values already identify an absolute instant.
    """
    if value is None:
        return datetime.now(UTC).replace(tzinfo=None)

    if value.tzinfo is None:
        station_zone = ZoneInfo(timezone_name)
        candidates = [value.replace(tzinfo=station_zone, fold=fold) for fold in (0, 1)]
        valid_candidates = [
            candidate
            for candidate in candidates
            if candidate.astimezone(UTC).astimezone(station_zone).replace(tzinfo=None) == value
        ]
        if not valid_candidates:
            raise ValueError("Thời điểm hiệu lực không tồn tại trong múi giờ trạm")
        if (
            len(valid_candidates) == 2
            and valid_candidates[0].utcoffset() != valid_candidates[1].utcoffset()
        ):
            raise ValueError("Thời điểm hiệu lực bị lặp trong múi giờ trạm; hãy gửi thời điểm kèm múi giờ")
        value = valid_candidates[0]

    return value.astimezone(UTC).replace(tzinfo=None)


def _paginate(query, page: int, size: int):
    """Phân trang đơn giản, trả về (items, total)"""
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return items, total


@router.get("", dependencies=[Depends(require_role("admin", "station_owner", "operator", "driver"))])
async def list_stations(
    current_user: CurrentUser,
    status: str | None = Query(None, description="Lọc theo trạng thái"),
    search: str = Query(None, description="Tìm kiếm"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Danh sách trạm của chủ trạm (hoặc tất cả nếu admin).
    Áp dụng lọc theo sở hữu ở tầng truy vấn — T-07."""
    role_names = [r.name for r in current_user.roles]
    q = db.query(Station).options(joinedload(Station.owner))
    driver_directory = "driver" in role_names and not {
        "admin", "station_owner", "operator"
    }.intersection(role_names)
    if driver_directory:
        # Drivers may browse public stations, but only those available for charging.
        q = q.filter(Station.status == "active")
    else:
        q = filter_by_owner(q, current_user.id, role_names)

    if status:
        q = q.filter(Station.status == status)
    if search:
        q = q.filter(Station.name.ilike(f"%{search}%"))

    q = q.order_by(Station.created_at.desc())

    items, total = _paginate(q, page, page_size)
    from app.models.charge_point import ChargePoint
    for item in items:
        item.charge_point_count = db.query(ChargePoint).filter(
            ChargePoint.station_id == item.id
        ).count()
    if driver_directory:
        items = [
            {
                "id": item.id,
                "name": item.name,
                "address": item.address,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "status": item.status,
                "created_at": item.created_at,
                "charge_point_count": item.charge_point_count,
            }
            for item in items
        ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get(
    "/{station_id}",
    response_model=StationResponse | StationDirectoryResponse,
    dependencies=[Depends(require_role("admin", "station_owner", "operator", "driver"))],
)
async def get_station(
    station_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Chi tiết một trạm — kiểm tra quyền sở hữu."""
    role_names = [r.name for r in current_user.roles]
    driver_directory = "driver" in role_names and not {
        "admin", "station_owner", "operator"
    }.intersection(role_names)
    if driver_directory:
        station = db.query(Station).filter(
            Station.id == station_id,
            Station.status == "active",
        ).first()
        if station is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy trạm")
        from app.models.charge_point import ChargePoint
        station.charge_point_count = db.query(ChargePoint).filter(
            ChargePoint.station_id == station_id
        ).count()
        return {
            "id": station.id,
            "name": station.name,
            "address": station.address,
            "latitude": station.latitude,
            "longitude": station.longitude,
            "status": station.status,
            "created_at": station.created_at,
            "charge_point_count": station.charge_point_count,
        }

    station = get_station_for_user(db, station_id, current_user.id, role_names, "view")
    if not station:
        raise HTTPException(status_code=404, detail="Không tìm thấy trạm")

    # Kiểm tra quyền sở hữu (admin thì bỏ qua)
    if "admin" not in role_names and "operator" not in role_names and station.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền xem trạm này",
        )

    # Đếm số trụ cho hiển thị trên danh sách
    from app.models.charge_point import ChargePoint
    station.charge_point_count = db.query(ChargePoint).filter(
        ChargePoint.station_id == station_id
    ).count()
    return station


@router.post("", response_model=StationResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_role("station_owner", "admin"))])
async def create_station(
    body: StationCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Tạo trạm mới — gắn với owner là user hiện tại.
    Chỉ chủ trạm và admin mới được tạo (T-09)."""
    role_names = [r.name for r in current_user.roles]
    if "station_owner" not in role_names and "admin" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ chủ trạm mới được tạo trạm",
        )
    if body.status == "locked" and "admin" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ quản trị viên mới được khóa trạm",
        )

    now = datetime.now(UTC).replace(tzinfo=None)
    station = Station(
        name=body.name,
        address=body.address,
        latitude=body.latitude,
        longitude=body.longitude,
        status=body.status,
        owner_id=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


@router.put("/{station_id}", response_model=StationResponse, dependencies=[Depends(require_role("station_owner", "admin"))])
async def update_station(
    station_id: int,
    body: StationUpdate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Sửa trạm — chỉ owner hoặc admin được sửa."""
    station = get_station_for_user(db, station_id, current_user.id, [r.name for r in current_user.roles], "update")
    if not station:
        raise HTTPException(status_code=404, detail="Không tìm thấy trạm")

    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names and station.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền sửa trạm này",
        )

    if (
        body.status is not None
        and "admin" not in role_names
        and (body.status == "locked" or station.status == "locked")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ quản trị viên mới được khóa hoặc mở khóa trạm",
        )

    if body.name is not None:
        station.name = body.name
    if body.address is not None:
        station.address = body.address
    if "latitude" in body.model_fields_set:
        station.latitude = body.latitude
    if "longitude" in body.model_fields_set:
        station.longitude = body.longitude
    if body.status is not None:
        station.status = body.status
    station.updated_at = datetime.now(UTC).replace(tzinfo=None)

    db.commit()
    db.refresh(station)
    return station


@router.delete("/{station_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_role("station_owner", "admin"))])
async def delete_station(
    station_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Xoá trạm — chỉ owner hoặc admin. Bị chặn nếu còn trụ (ON DELETE RESTRICT)."""
    station = get_station_for_user(db, station_id, current_user.id, [r.name for r in current_user.roles], "delete")
    if not station:
        raise HTTPException(status_code=404, detail="Không tìm thấy trạm")

    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names and station.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền xoá trạm này",
        )

    db.delete(station)
    db.commit()
