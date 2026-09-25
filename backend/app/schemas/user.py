"""
schemas/user.py -- Pydantic schema cho auth
Tham chieu: SPRINT_1.md T-05
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
