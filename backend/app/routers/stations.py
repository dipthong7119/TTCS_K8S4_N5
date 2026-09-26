"""
routers/stations.py -- CRUD trạm sạc (S-04, T-09)
Tham chieu: SPRINT_1.md T-08, T-09, SSD-1, 02_CODING_STANDARDS.md
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.models.station import Station
from app.schemas.station import StationCreate, StationResponse, StationUpdate
from app.services.ownership import filter_by_owner, get_station_for_user

router = APIRouter(prefix="/stations", tags=["stations"], dependencies=[Depends(deny_unannotated_route)])


def _paginate(query, page: int, size: int):
    """Phân trang đơn giản, trả về (items, total)"""
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return items, total


@router.get("", dependencies=[Depends(require_role("admin", "station_owner", "operator"))])
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
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{station_id}", response_model=StationResponse, dependencies=[Depends(require_role("admin", "station_owner", "operator"))])
async def get_station(
    station_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Chi tiết một trạm — kiểm tra quyền sở hữu."""
    role_names = [r.name for r in current_user.roles]
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
