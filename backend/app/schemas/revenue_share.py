"""Contracts for splitting partner and platform subscription revenue."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RevenueShareContractCreate(BaseModel):
    station_owner_id: int = Field(gt=0)
    partner_share_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    platform_share_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    effective_from: datetime

    @model_validator(mode="after")
    def percentages_must_total_one_hundred(self):
        if self.partner_share_percent + self.platform_share_percent != Decimal(100):
            raise ValueError("Tổng tỉ lệ đối tác và nền tảng phải bằng 100%")
        return self


class RevenueShareContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    station_owner_id: int
    partner_name: str
    partner_email: str
    partner_share_percent: Decimal
    platform_share_percent: Decimal
    effective_from: datetime
    effective_to: datetime | None
