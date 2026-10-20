"""Request models for financial reconciliation period closing."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ReconciliationPeriodLockRequest(BaseModel):
    station_id: int = Field(gt=0)
    from_date: date
    to_date: date

    @model_validator(mode="after")
    def dates_are_ordered(self):
        if self.from_date > self.to_date:
            raise ValueError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")
        return self


class ReconciliationPeriodReopenRequest(BaseModel):
    station_id: int = Field(gt=0)
    from_date: date
    to_date: date
    charge_point_code: str | None = Field(default=None, min_length=1)
    status: Literal[
        "all",
        "review",
        "missing_invoice",
        "missing_ledger",
        "amount_mismatch",
        "collection_mismatch",
        "missing_pricing",
    ] = "all"
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def dates_are_ordered(self):
        if self.from_date > self.to_date:
            raise ValueError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")
        return self

    @field_validator("reason")
    @classmethod
    def blank_reason_is_empty(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None
