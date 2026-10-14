"""API huỷ đặt chỗ của tài xế (S-51: Tài xế huỷ chỗ đã đặt và trụ mở lại cho người khác)."""

import logging

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import deny_unannotated_route, require_role
from app.database import get_db
from app.models.user import User
from app.schemas.reservation import (
    CancelReservationResponse,
    ReservationErrorResponse,
)
from app.services.reservations import (
    ReservationCancelError,
    cancel_reservation,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/reservations",
    tags=["reservations"],
    dependencies=[Depends(deny_unannotated_route)],
)


@router.post(
    "/{reservation_id}/cancel",
    response_model=CancelReservationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "model": CancelReservationResponse,
            "description": "Huỷ đặt chỗ thành công",
        },
        401: {
            "model": ReservationErrorResponse,
            "description": "Chưa đăng nhập",
        },
        403: {
            "model": ReservationErrorResponse,
            "description": "Không có quyền hoặc không thuộc về người dùng",
        },
        409: {
            "model": ReservationErrorResponse,
            "description": "Xung đột trạng thái không thể huỷ",
        },
    },
)
async def cancel_reservation_endpoint(
    reservation_id: int,
    current_user: User = Depends(require_role("driver")),
    db: Session = Depends(get_db),
):
    """Tài xế huỷ chỗ đã đặt trước hạn (S-51)."""
    try:
        data = await cancel_reservation(db, reservation_id, current_user.id)
        return data
    except ReservationCancelError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "code": exc.code},
        )
