"""
Pydantic Schemas: alerts
Tham chiếu: SCRUM-90 / S-46 — Cảnh báo giám sát vận hành.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AlertResolveRequest(BaseModel):
    note: str | None = Field(
        default=None,
        max_length=500,
        description="Ghi chú phương án xử lý sự cố khi đóng cảnh báo",
    )


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    charge_point_id: int
    charge_point_code: str | None = None
    station_name: str | None = None
    connector_id: int | None = None
    error_code: str | None = None
    alert_type: Literal["offline", "connector_error"]
    severity: Literal["warning", "critical"]
    status: Literal["active", "resolved"]
    message: str
    error_count: int | None = None
    triggered_at: datetime
    resolved_at: datetime | None = None
    resolved_by_id: int | None = None
    created_at: datetime
    updated_at: datetime


class AlertListResponse(BaseModel):
    total: int
    items: list[AlertResponse]
    active_count: int = 0
