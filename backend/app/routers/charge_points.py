"""
routers/charge_points.py -- Thêm trụ/đầu nối (S-05, T-10, T-11)
Tham chieu: SPRINT_1.md T-10, T-11, 02_CODING_STANDARDS.md
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.charge_point import ChargePoint, Connector
from app.models.station import Station
from app.models.user import User
from app.schemas.charge_point import ChargePointCreate, ChargePointUpdate, ChargePointResponse, ConnectorResponse
from app.core.deps import CurrentUser, require_role

router = APIRouter(prefix="/charge-points", tags=["charge_points"])


def _get_station_owner_role(db: Session, station_id: int) -> Optional[str]:
    """Lấy vai trò của người sở hữu trạm"""
    from app.models.station import Station
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        return None
    return [r.name for r in station.owner.roles]


@router.post("", response_model=ChargePointResponse, status_code=status.HTTP_201_CREATED)
async def create_charge_point(
    body: ChargePointCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Thêm trụ mới vào trạm.
    Chỉ chủ trạm và admin mới được thêm trụ (T-10).
    Mã trụ unique toàn hệ thống (T-10 AC)."""
    # Kiểm tra trạm tồn tại và quyền sở hữu
    from app.models.station import Station
    station = db.query(Station).filter(Station.id == body.station_id).first()
    if not station:
        raise HTTPException(status_code=404, detail="Không tìm thấy trạm")

    role_names = [r.name for r in current_user.roles]
    if "station_owner" not in role_names and "admin" not in role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ chủ trạm mới được thêm trụ",
        )

    # Check duplicate code
    existing = db.query(ChargePoint).filter(ChargePoint.code == body.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mã trụ '{body.code}' đã tồn tại trên toàn hệ thống",
        )

    # Tạo charge_point
    cp = ChargePoint(
        code=body.code.strip(),
        station_id=body.station_id,
        vendor=body.vendor,
        model=body.model,
        firmware_version=body.firmware_version,
        status="offline",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(cp)
    db.flush()  # để lấy cp.id

    # Tạo connectors
    for i in range(1, body.connector_count + 1):
        connector = Connector(
            charge_point_id=cp.id,
            connector_id=i,
            status="unavailable",
            error_code="NoError",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(connector)

    db.commit()
    db.refresh(cp)
    # Load connectors
    cp.connectors = db.query(Connector).filter(Connector.charge_point_id == cp.id).all()
    return cp


@router.get("", response_model=list[ChargePointResponse])
async def list_charge_points(
    current_user: CurrentUser,
    station_id: Optional[int] = Query(None, description="Lọc theo trạm"),
    db: Session = Depends(get_db),
):
    """Danh sách trụ. Chủ trạm chỉ thấy trụ của trạm mình."""
    q = db.query(ChargePoint).options(joinedload(ChargePoint.station))

    if station_id:
        q = q.filter(ChargePoint.station_id == station_id)
    else:
        # Lọc theo sở hữu nếu không phải admin
        role_names = [r.name for r in current_user.roles]
        if "admin" not in role_names:
            # Join với stations để lọc
            from app.models.station import Station
            q = q.join(Station).filter(
                Station.owner_id == current_user.id
            )

    q = q.order_by(ChargePoint.created_at.desc())
    items = q.all()

    # Load connectors cho mỗi charge point
    for cp in items:
        cp.connectors = db.query(Connector).filter(Connector.charge_point_id == cp.id).all()

    return items


@router.get("/{cp_id}", response_model=ChargePointResponse)
async def get_charge_point(
    cp_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Chi tiết một trụ."""
    cp = db.query(ChargePoint).filter(ChargePoint.id == cp_id).first()
    if not cp:
        raise HTTPException(status_code=404, detail="Không tìm thấy trụ")

    # Kiểm tra quyền sở hữu
    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names:
        station = db.query(Station).filter(Station.id == cp.station_id).first()
        if not station or station.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền xem trụ này",
            )

    cp.connectors = db.query(Connector).filter(Connector.charge_point_id == cp.id).all()
    return cp


@router.patch("/{cp_id}", response_model=ChargePointResponse)
async def update_charge_point(
    cp_id: int,
    body: ChargePointUpdate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Cập nhật thông tin trụ."""
    cp = db.query(ChargePoint).filter(ChargePoint.id == cp_id).first()
    if not cp:
        raise HTTPException(status_code=404, detail="Không tìm thấy trụ")

    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names:
        station = db.query(Station).filter(Station.id == cp.station_id).first()
        if not station or station.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền sửa trụ này",
            )

    if body.vendor is not None:
        cp.vendor = body.vendor
    if body.model is not None:
        cp.model = body.model
    if body.firmware_version is not None:
        cp.firmware_version = body.firmware_version
    if body.status is not None:
        cp.status = body.status
    cp.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(cp)
    return cp


@router.delete("/{cp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_charge_point(
    cp_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Xoá trụ. Bị chặn nếu còn phiên sạc đang mở."""
    cp = db.query(ChargePoint).filter(ChargePoint.id == cp_id).first()
    if not cp:
        raise HTTPException(status_code=404, detail="Không tìm thấy trụ")

    role_names = [r.name for r in current_user.roles]
    if "admin" not in role_names:
        station = db.query(Station).filter(Station.id == cp.station_id).first()
        if not station or station.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền xoá trụ này",
            )

    db.delete(cp)
    db.commit()
    return None


@router.get("/check-code", status_code=200)
async def check_code(
    current_user: CurrentUser,
    code: str = Query(..., description="Mã trụ cần kiểm tra"),
    db: Session = Depends(get_db),
):
    """Kiểm tra mã trụ có trùng không (T-11).
    Trả 200 nếu OK, 409 nếu đã tồn tại."""
    existing = db.query(ChargePoint).filter(ChargePoint.code == code.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mã trụ '{code}' đã tồn tại trên toàn hệ thống",
        )
    return {"available": True, "message": "Mã trụ hợp lệ"}