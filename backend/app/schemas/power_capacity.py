"""Request and response schemas for station power capacity (SCRUM-80)."""

from decimal import Decimal

from pydantic import BaseModel, Field


class ConnectorPowerCapacityInput(BaseModel):
    charge_point_code: str = Field(min_length=1, max_length=50)
    connector_id: int = Field(gt=0)
    rated_power_kw: Decimal = Field(gt=0, max_digits=10, decimal_places=3)


class StationPowerCapacityUpdate(BaseModel):
    power_limit_kw: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    connectors: list[ConnectorPowerCapacityInput]


class ConnectorPowerCapacityResponse(BaseModel):
    charge_point_code: str
    connector_id: int
    rated_power_kw: Decimal | None


class StationPowerCapacityResponse(BaseModel):
    station_id: int
    power_limit_kw: Decimal | None
    nominal_power_kw: Decimal
    over_subscribed: bool
    missing_connector_count: int
    connectors: list[ConnectorPowerCapacityResponse]
