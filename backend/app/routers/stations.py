"""
routers/stations.py -- CRUD trạm sạc (S-04, T-09)
Tham chieu: SPRINT_1.md T-08, T-09, SSD-1, 02_CODING_STANDARDS.md
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.charge_point import ChargePoint, Connector
from app.models.charging_invoice import ChargingInvoice
from app.models.charging_session import ChargingSession
from app.models.reservation import Reservation, ReservationStatus
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
from app.services.connection_manager import manager
from app.services.ocpp_status import is_charge_point_stale
from app.services.pricing import normalize_daily_bands

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
        "bands": [
            {
                "label": band.label,
                "start_minute": band.start_minute,
                "end_minute": band.end_minute,
                "price_vnd_per_kwh": band.price_vnd_per_kwh,
            }
            for band in tariff.bands
        ],
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


@router.get(
    "/{station_id}/revenue",
    dependencies=[Depends(require_role("station_owner", "admin"))],
)
async def get_station_revenue(
    station_id: int,
    current_user: CurrentUser,
    start_date: date | None = Query(None, description="Ngày bắt đầu, bao gồm cả ngày này"),
    end_date: date | None = Query(None, description="Ngày kết thúc, bao gồm cả ngày này"),
    db: Session = Depends(get_db),
):
    """Summarize finalized revenue and energy by charger for a station-local date range."""
    roles = [role.name for role in current_user.roles]
    station = get_station_for_user(db, station_id, current_user.id, roles, "view_revenue")

    latest_tariff = (
        db.query(StationTariff)
        .filter(StationTariff.station_id == station_id, StationTariff.is_demo.is_(False))
        .order_by(StationTariff.effective_from.desc(), StationTariff.id.desc())
        .first()
    )
    timezone_name = latest_tariff.timezone_name if latest_tariff else "Asia/Ho_Chi_Minh"
    try:
        station_zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        station_zone = ZoneInfo("Asia/Ho_Chi_Minh")
        timezone_name = "Asia/Ho_Chi_Minh"

    local_today = datetime.now(UTC).astimezone(station_zone).date()
    start_date = start_date or local_today.replace(day=1)
    end_date = end_date or local_today
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")

    # Database datetimes are naive UTC; interpret the requested inclusive dates
    # as calendar dates in the station's configured timezone.
    start_utc = (
        datetime.combine(start_date, time.min, tzinfo=station_zone)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )
    end_utc = (
        datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=station_zone)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )

    charge_points = (
        db.query(ChargePoint)
        .filter(ChargePoint.station_id == station_id)
        .order_by(ChargePoint.code)
        .all()
    )
    stats: dict[str, dict] = {
        point.code: {
            "charge_point_code": point.code,
            "session_count": 0,
            "total_kwh": 0.0,
            "revenue_vnd": 0,
            "occupancy_fee_vnd": 0,
        }
        for point in charge_points
    }
    finalized_sessions = (
        db.query(ChargingSession, ChargingInvoice)
        .join(ChargingInvoice, ChargingInvoice.session_id == ChargingSession.id)
        .filter(
            ChargingSession.station_id == station_id,
            ChargingSession.started_at >= start_utc,
            ChargingSession.started_at < end_utc,
            ChargingSession.status == "completed",
            ChargingSession.is_demo.is_(False),
            ChargingInvoice.is_demo.is_(False),
        )
        .all()
    )
    total_kwh = 0.0
    total_revenue_vnd = 0
    total_occupancy_fee_vnd = 0
    for session, invoice in finalized_sessions:
        row = stats.setdefault(
            session.charge_point_code,
            {
                "charge_point_code": session.charge_point_code,
                "session_count": 0,
                "total_kwh": 0.0,
                "revenue_vnd": 0,
                "occupancy_fee_vnd": 0,
            },
        )
        energy = float(session.energy_kwh or 0)
        revenue = int(invoice.total_vnd or 0)
        occupancy_fee = sum(
            int(segment.get("amount_vnd", 0))
            for segment in (invoice.segments or [])
            if segment.get("kind") == "occupancy_fee"
        )
        row["session_count"] += 1
        row["total_kwh"] += energy
        row["revenue_vnd"] += revenue
        row["occupancy_fee_vnd"] += occupancy_fee
        total_kwh += energy
        total_revenue_vnd += revenue
        total_occupancy_fee_vnd += occupancy_fee

    return {
        "station_id": station.id,
        "station_name": station.name,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timezone": timezone_name,
        "session_count": len(finalized_sessions),
        "total_kwh": round(total_kwh, 3),
        "revenue_vnd": total_revenue_vnd,
        "occupancy_fee_vnd": total_occupancy_fee_vnd,
        "charge_points": [
            {**row, "total_kwh": round(row["total_kwh"], 3)}
            for row in sorted(stats.values(), key=lambda item: item["charge_point_code"])
        ],
    }


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

    try:
        if body.bands is not None:
            band_data = normalize_daily_bands(body.bands)
        else:
            assert body.price_vnd_per_kwh is not None
            band_data = [
                {
                    "label": "Cả ngày",
                    "start_minute": 0,
                    "end_minute": 1440,
                    "price_vnd_per_kwh": body.price_vnd_per_kwh,
                }
            ]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    tariff = StationTariff(
        station_id=station.id,
        name=tariff_name,
        timezone_name=body.timezone_name,
        effective_from=effective_from,
        occupancy_fee_vnd_per_minute=body.occupancy_fee_vnd_per_minute,
        grace_period_minutes=body.grace_period_minutes,
        is_demo=False,
        bands=[TariffBand(**band) for band in band_data],
    )
    db.add(tariff)
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
    "/{station_id}/booking-options",
    dependencies=[Depends(require_role("driver"))],
)
async def get_station_booking_options(
    station_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Return only public, currently bookable connector identifiers to drivers."""
    station = db.query(Station).filter(
        Station.id == station_id,
        Station.status == "active",
    ).first()
    if station is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy trạm đang hoạt động")

    now = datetime.now(UTC).replace(tzinfo=None)
    active_reservations = (
        db.query(Reservation.charge_point_id, Reservation.connector_id)
        .filter(
            Reservation.status.in_([
                ReservationStatus.PENDING,
                ReservationStatus.ACTIVE,
            ]),
            Reservation.expiry_date > now,
            Reservation.charge_point_id.in_(
                db.query(ChargePoint.id).filter(ChargePoint.station_id == station.id)
            ),
        )
        .all()
    )
    reserved_slots = {(row.charge_point_id, row.connector_id) for row in active_reservations}

    points = (
        db.query(ChargePoint)
        .options(joinedload(ChargePoint.connectors))
        .filter(ChargePoint.station_id == station.id)
        .order_by(ChargePoint.code)
        .all()
    )
    busy_statuses = {
        "charging", "suspended_ev", "suspended_evse", "finishing",
        "reserved", "faulted", "unavailable",
    }
    busy_ocpp_statuses = {
        "Charging", "SuspendedEV", "SuspendedEVSE", "Finishing",
        "Reserved", "Faulted", "Unavailable", "Occupied",
    }

    items = []
    for point in points:
        point_online = (
            point.code in manager.active_connections
            and point.status == "online"
            and not is_charge_point_stale(point.last_seen_at)
        )
        if not point_online:
            continue

        available_connectors = [
            {
                "connector_id": connector.connector_id,
                "connector_type": connector.connector_type,
                "rated_power_kw": connector.rated_power_kw,
            }
            for connector in point.connectors
            if connector.status.lower() not in busy_statuses
            and connector.ocpp_status not in busy_ocpp_statuses
            and (point.id, connector.connector_id) not in reserved_slots
        ]
        if available_connectors:
            items.append({
                "charge_point_code": point.code,
                "connectors": available_connectors,
            })

    return {"station_id": station.id, "station_name": station.name, "items": items}


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
        no_show_fee_vnd=body.no_show_fee_vnd,
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
    if body.no_show_fee_vnd is not None:
        station.no_show_fee_vnd = body.no_show_fee_vnd
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
