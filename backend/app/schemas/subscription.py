"""Request and response schemas for monthly charging plans."""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SubscriptionPlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    monthly_fee_vnd: int = Field(gt=0)
    price_vnd_per_kwh: int = Field(ge=0)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Tên gói không được để trống")
        return normalized


class SubscriptionPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    monthly_fee_vnd: int | None = Field(default=None, gt=0)
    price_vnd_per_kwh: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Tên gói không được để trống")
        return normalized

    @model_validator(mode="after")
    def validate_patch(self) -> "SubscriptionPlanUpdate":
        for field in ("name", "monthly_fee_vnd", "price_vnd_per_kwh", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"Trường {field} không được để trống")
        if not self.model_fields_set:
            raise ValueError("Cần cung cấp ít nhất một trường để cập nhật")
        return self


class SubscriptionPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    monthly_fee_vnd: int
    price_vnd_per_kwh: int
    is_active: bool


class SubscribeRequest(BaseModel):
    plan_id: int = Field(gt=0)
