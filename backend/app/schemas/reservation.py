"""
Schemas: reservations (SCRUM-76 / S-48: Tài xế đặt chỗ trụ sạc).
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ReservationCreateRequest(BaseModel):
    """Payload gửi lên từ tài xế/FE khi tạo đặt chỗ."""

    charge_point_code: str = Field(..., description="Mã trụ sạc (code)")
    connector_id: int = Field(..., ge=1, description="Số đầu nối (bắt đầu từ 1)")
    start_time: datetime | None = Field(
        None,
        description="Thời gian bắt đầu dự kiến (mặc định là thời điểm hiện tại)",
    )
    expiry_date: datetime | None = Field(
        None,
        description="Thời hạn giữ chỗ (ISO 8601, tối đa trong vòng 2 giờ tới)",
    )
    expiry_minutes: int | None = Field(
        None,
        ge=5,
        le=120,
        description="Số phút giữ chỗ (5 - 120 phút), thay thế nếu không truyền expiry_date",
    )
    id_tag: str | None = Field(
        None,
        description="Mã thẻ RFID hoặc Virtual idTag của tài xế (mặc định lấy thẻ đang kích hoạt của tài xế)",
    )


class ReservationItem(BaseModel):
    """Thông tin chi tiết một bản ghi đặt chỗ."""

    id: int
    charge_point_id: int
    charge_point_code: str
    connector_id: int
    user_id: int
    id_tag: str
    start_time: datetime
    expiry_date: datetime
    status: str
    reject_reason: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReservationCreateResponse(BaseModel):
    """Kết quả trả về khi tạo đặt chỗ."""

    status: str  # "Accepted", "Rejected", "Occupied", "Unavailable", "Faulted"
    message: str
    reservation: ReservationItem | None = None
