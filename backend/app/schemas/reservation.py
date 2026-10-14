"""Schemas for reservation endpoints (S-51: Driver cancel reservation)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CancelReservationResponse(BaseModel):
    """Thông tin phản hồi khi huỷ đặt chỗ thành công (200)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    cancelled_at: datetime
    cancel_status: str


class ReservationErrorResponse(BaseModel):
    """Thông tin phản hồi lỗi (409, 403, 401, 404)."""

    detail: str
    code: str
