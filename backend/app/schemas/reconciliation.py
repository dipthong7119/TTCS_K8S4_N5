"""Request models for financial reconciliation period closing."""

from datetime import date

from pydantic import BaseModel, Field, model_validator


class ReconciliationPeriodLockRequest(BaseModel):
    station_id: int = Field(gt=0)
    from_date: date
    to_date: date

    @model_validator(mode="after")
    def dates_are_ordered(self):
        if self.from_date > self.to_date:
            raise ValueError("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc")
        return self
