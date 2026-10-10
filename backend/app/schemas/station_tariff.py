"""Request and response schemas for owner-managed station tariffs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StationTariffBandCreate(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    start_minute: int = Field(ge=0, lt=1440)
    end_minute: int = Field(ge=0, le=1440)
    price_vnd_per_kwh: int = Field(ge=0, le=1_000_000_000)


class StationTariffCreate(BaseModel):
    name: str = Field(default="Biểu giá trạm", min_length=1, max_length=120)
    price_vnd_per_kwh: int | None = Field(default=None, ge=0, le=1_000_000_000)
    bands: list[StationTariffBandCreate] | None = Field(default=None, min_length=1)
    occupancy_fee_vnd_per_minute: int = Field(default=0, ge=0, le=1_000_000_000)
    grace_period_minutes: int = Field(default=0, ge=0, le=100_000)
    effective_from: datetime | None = None
    timezone_name: str = Field(default="Asia/Ho_Chi_Minh", max_length=80)

    @model_validator(mode="after")
    def require_flat_rate_or_bands(self):
        if (self.price_vnd_per_kwh is None) == (self.bands is None):
            raise ValueError("Cần khai báo đơn giá cả ngày hoặc danh sách khung giờ")
        return self


class StationTariffBandResponse(BaseModel):
    label: str
    start_minute: int
    end_minute: int
    price_vnd_per_kwh: int


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
    bands: list[StationTariffBandResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
