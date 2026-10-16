"""
Router: reservations (SCRUM-76 / S-48: API đặt chỗ trụ sạc).
"""


from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import deny_unannotated_route, require_role
from app.database import get_db
from app.models.user import User
from app.schemas.reservation import (
    CancelReservationResponse,
    ReservationCreateRequest,
    ReservationCreateResponse,
    ReservationErrorResponse,
    ReservationItem,
)
from app.services.reservation import (
    create_reservation,
    get_reservation_by_id,
    get_user_reservations,
)
from app.services.reservations import ReservationCancelError, cancel_reservation

router = APIRouter(
    prefix="/reservations",
    tags=["reservations"],
    dependencies=[Depends(deny_unannotated_route)],
)


@router.post(
    "",
    response_model=ReservationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reservation_endpoint(
    payload: ReservationCreateRequest,
    current_user: User = Depends(require_role("driver", "operator", "admin")),
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
)
def list_my_reservations_endpoint(
    active_only: bool = Query(False, description="Chỉ lấy các lượt đặt chỗ đang có hiệu lực"),
    current_user: User = Depends(require_role("driver", "operator", "admin")),
    db: Session = Depends(get_db),
):
    """Lấy danh sách các lượt đặt chỗ của tài xế hiện tại."""
    return get_user_reservations(db, current_user, active_only=active_only)


@router.get(
    "/{reservation_id}",
    response_model=ReservationItem,
)
def get_reservation_detail_endpoint(
    reservation_id: int,
    current_user: User = Depends(require_role("driver", "operator", "admin")),
    db: Session = Depends(get_db),
):
    """Xem chi tiết một lượt đặt chỗ theo ID."""
    return get_reservation_by_id(db, current_user, reservation_id)


@router.post(
    "/{reservation_id}/cancel",
    response_model=CancelReservationResponse,
    responses={
        401: {"model": ReservationErrorResponse},
        403: {"model": ReservationErrorResponse},
        409: {"model": ReservationErrorResponse},
    },
)
async def cancel_reservation_endpoint(
    reservation_id: int,
    current_user: User = Depends(require_role("driver")),
    db: Session = Depends(get_db),
):
    """Tài xế huỷ chỗ đã đặt trước thời hạn cho phép (SCRUM-79)."""
    try:
        return await cancel_reservation(db, reservation_id, current_user.id)
    except ReservationCancelError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "code": exc.code},
        )
