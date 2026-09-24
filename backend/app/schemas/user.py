"""
schemas/user.py -- Pydantic schema cho auth
Tham chieu: SPRINT_1.md T-05
"""

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    message: str
    user_id: int
    email: str
    full_name: str
    roles: list[str]
