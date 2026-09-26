"""
schemas/station.py -- Pydantic request/response cho stations (S-04, T-09)
Tham chieu: SPRINT_1.md T-08, T-09
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


# -- Request ---
class StationCreate(BaseModel):
    name: str = Field(..., max_length=255, example="Trạm sạc Quận 1")
    address: str = Field(..., example="123 Đường Chính, Phường A, Quận 1")
    latitude: Optional[float] = Field(None, ge=-90, le=90, example=10.762622)
    longitude: Optional[float] = Field(None, ge=-180, le=180, example=106.660172)
    status: str = Field("active", pattern="^(active|inactive|maintenance)$")


class StationUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    status: Optional[str] = Field(None, pattern="^(active|inactive|maintenance)$")


# -- Response ---
class StationResponse(BaseModel):
    id: int
    name: str
    address: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    status: str
    owner_id: int
    created_at: datetime
    updated_at: datetime
    charge_point_count: int = 0  # số trụ trong trạm (hiển thị trên danh sách)

    model_config = ConfigDict(from_attributes=True)