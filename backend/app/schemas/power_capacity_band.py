"""Request and response schemas for SCRUM-83 power bands."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PowerCapacityBandInput(BaseModel):
    start_minute: int = Field(ge=0, lt=1440)
    end_minute: int = Field(ge=0, le=1440)
    power_limit_kw: Decimal = Field(gt=0, max_digits=10, decimal_places=3)

    @model_validator(mode="after")
    def require_nonempty_band(self):
        if self.start_minute == self.end_minute:
            raise ValueError("Giờ bắt đầu và kết thúc không được trùng nhau")
        return self


class PowerCapacityBandResponse(BaseModel):
    id: int
    station_id: int
    start_minute: int
    end_minute: int
    power_limit_kw: Decimal
    timezone_name: str

    model_config = ConfigDict(from_attributes=True)
