"""
Router: reservations (SCRUM-76 / S-48: API đặt chỗ trụ sạc).
"""


from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, deny_unannotated_route, require_role
from app.database import get_db
from app.schemas.reservation import (
    ReservationCreateRequest,
    ReservationCreateResponse,
    ReservationItem,
)
from app.services.reservation import (
    create_reservation,
    get_reservation_by_id,
    get_user_reservations,
)

router = APIRouter(
    prefix="/reservations",
    tags=["reservations"],
    dependencies=[Depends(deny_unannotated_route)],
)


@router.post(
    "",
    response_model=ReservationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("driver", "operator", "admin"))],
)
async def create_reservation_endpoint(
    payload: ReservationCreateRequest,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    """Tạo yêu cầu đặt trước trụ sạc (SCRUM-76 / S-48).
    
    Kiểm tra điều kiện tài xế, gửi lệnh OCPP ReserveNow xuống trụ sạc.
    Khi trụ chấp nhận, đầu nối được chuyển sang trạng thái Reserved.
    """
    return await create_reservation(db, current_user, payload)


@router.get(
    "/me",
    response_model=list[ReservationItem],
    dependencies=[Depends(require_role("driver", "operator", "admin"))],
)
def list_my_reservations_endpoint(
    active_only: bool = Query(False, description="Chỉ lấy các lượt đặt chỗ đang có hiệu lực"),
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Lấy danh sách các lượt đặt chỗ của tài xế hiện tại."""
    return get_user_reservations(db, current_user, active_only=active_only)


@router.get(
    "/{reservation_id}",
    response_model=ReservationItem,
    dependencies=[Depends(require_role("driver", "operator", "admin"))],
)
def get_reservation_detail_endpoint(
    reservation_id: int,
    current_user: CurrentUser = None,
    db: Session = Depends(get_db),
):
    """Xem chi tiết một lượt đặt chỗ theo ID."""
    return get_reservation_by_id(db, current_user, reservation_id)
