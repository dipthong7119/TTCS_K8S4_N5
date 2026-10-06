"""
schemas/user.py -- Pydantic schema cho auth
Tham chieu: SPRINT_1.md T-05, SCRUM-135
"""

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


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
