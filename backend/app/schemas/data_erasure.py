"""
Pydantic Schemas for Data Erasure / Privacy Requests (SCRUM-92 / S-57).
Tham chiếu: Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DataErasureCreateRequest(BaseModel):
    """Payload gửi yêu cầu xóa dữ liệu cá nhân của tài xế."""

    reason: str | None = Field(
        None, max_length=500, description="Lý do yêu cầu xóa dữ liệu cá nhân"
    )
    reason_label: str | None = Field(None, max_length=255)
    reason_detail: str | None = Field(None, max_length=2000)


class PrivacyDeletionCreateRequest(BaseModel):
    """Payload used by the privacy page, including password confirmation."""

    reason: str = Field(..., min_length=1, max_length=500)
    reason_label: str | None = Field(None, max_length=255)
    reason_detail: str | None = Field(None, max_length=2000)
    password: str = Field(..., min_length=1, max_length=128)


class PrivacyDeletionRejectRequest(BaseModel):
    """Compatibility payload expected by the privacy administration page."""

    reason: str = Field(..., min_length=3, max_length=500)


class DataErasureRejectRequest(BaseModel):
    """Payload từ chối yêu cầu xóa dữ liệu từ quản trị viên."""

    rejection_reason: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Lý do bắt buộc khi từ chối yêu cầu",
    )


class DataErasureResponse(BaseModel):
    """Thông tin chi tiết một yêu cầu xóa/ẩn danh hóa dữ liệu."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    driver_name: str | None = None
    driver_email: str | None = None
    status: str
    resolution_action: str | None = None
    request_reason: str | None = None
    rejection_reason: str | None = None
    requested_at: datetime
    processed_at: datetime | None = None
    processed_by: int | None = None
    processor_name: str | None = None
    created_at: datetime
    updated_at: datetime


class DataErasureListResponse(BaseModel):
    """Danh sách các yêu cầu xóa dữ liệu phân trang."""

    items: list[DataErasureResponse]
    total: int
    skip: int
    limit: int
