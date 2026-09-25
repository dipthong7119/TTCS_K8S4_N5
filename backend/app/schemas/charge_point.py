"""
schemas/charge_point.py -- Pydantic request/response cho charge_points/connectors (S-05, T-11)
Tham chieu: SPRINT_1.md T-10, T-11
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# -- Request ---
class ChargePointCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, example="T-01")
    station_id: int = Field(..., gt=0, example=1)
    vendor: str | None = Field(None, max_length=255, example="ABB")
    model: str | None = Field(None, max_length=255, example="Terra AC")
    firmware_version: str | None = Field(None, max_length=100, example="1.0.0")
    connector_count: int = Field(1, ge=1, le=4, example=2)

    @field_validator("code")
    @classmethod
    def strip_code(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Mã trụ không được để trống")
        return value


class ChargePointUpdate(BaseModel):
    vendor: str | None = Field(None, max_length=255)
    model: str | None = Field(None, max_length=255)
    firmware_version: str | None = Field(None, max_length=100)
    status: str | None = Field(None, pattern="^(online|offline)$")


# -- Response ---
class ConnectorResponse(BaseModel):
    id: int
    charge_point_id: int
    connector_id: int
    status: str
    error_code: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChargePointResponse(BaseModel):
    id: int
    code: str
    station_id: int
    vendor: str | None
    model: str | None
    firmware_version: str | None
    status: str
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
    connectors: list[ConnectorResponse] = []

    model_config = ConfigDict(from_attributes=True)