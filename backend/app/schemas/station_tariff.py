"""Request and response schemas for owner-managed station tariffs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StationTariffCreate(BaseModel):
    name: str = Field(default="Biểu giá trạm", min_length=1, max_length=120)
    price_vnd_per_kwh: int = Field(ge=0, le=1_000_000_000)
    occupancy_fee_vnd_per_minute: int = Field(default=0, ge=0, le=1_000_000_000)
    grace_period_minutes: int = Field(default=0, ge=0, le=100_000)
    effective_from: datetime | None = None
    timezone_name: str = Field(default="Asia/Ho_Chi_Minh", max_length=80)


class StationTariffResponse(BaseModel):
    id: int
    station_id: int
    name: str
    timezone_name: str
    effective_from: datetime
    occupancy_fee_vnd_per_minute: int
    grace_period_minutes: int
    is_demo: bool
    price_vnd_per_kwh: int | None

    model_config = ConfigDict(from_attributes=True)
