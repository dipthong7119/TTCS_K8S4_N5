"""
schemas/user.py -- Pydantic schema cho auth
Tham chieu: SPRINT_1.md T-05, SCRUM-135
"""

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    email: str
    password: str


class DriverRegisterRequest(BaseModel):
    """Thông tin tối thiểu để tự tạo một tài khoản tài xế."""

    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name", mode="before")
    @classmethod
    def normalize_full_name(cls, value):
        if isinstance(value, str):
            return " ".join(value.split())
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if isinstance(value, str):
            return value.strip().lower()
        return value


class DriverRegisterResponse(BaseModel):
    message: str
    email: str


class LoginResponse(BaseModel):
    message: str
    user_id: int
    email: str
    full_name: str
    roles: list[str]
    redirect_to: str


class MeResponse(BaseModel):
    """Thong tin nguoi dung hien tai -- dung boi route_guard.js (SCRUM-135)."""
    user_id: int
    email: str
    full_name: str
    roles: list[str]
    # Nhan hien thi tieng Viet cua role chinh (role co priority cao nhat)
    role_label: str
