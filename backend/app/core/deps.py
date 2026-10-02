"""
deps.py -- FastAPI Dependencies: current_user, require_role(...)
Tham chieu: SPRINT_1.md T-06, SSD-1, 02_CODING_STANDARDS.md
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User


def public_route(endpoint):
    """Mark an endpoint as intentionally public (for example, login)."""
    endpoint.__public_route__ = True
    return endpoint


def _has_role_guard(dependant) -> bool:
    for dependency in getattr(dependant, "dependencies", ()):
        if getattr(dependency.call, "__role_guard__", False):
            return True
        if _has_role_guard(dependency):
            return True
    return False


async def deny_unannotated_route(request: Request) -> None:
    """Deny API routes unless they declare a role guard or are explicitly public."""
    route = request.scope.get("route")
    endpoint = getattr(route, "endpoint", None)
    if getattr(endpoint, "__public_route__", False):
        return
    if _has_role_guard(getattr(route, "dependant", None)):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Route chua khai bao quyen truy cap",
    )


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """
    Lay user hien tai tu session cookie.
    Tra ve 401 neu chua dang nhap hoac session het han.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chua dang nhap",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tai khoan khong ton tai hoac da bi khoa",
        )

    # Kiem tra lockout (them lop bao ve)
    if user.locked_until and user.locked_until > datetime.now(UTC).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="tai khoan tam khoa 15 phut",
        )

    return user


def require_role(*allowed_roles: str):
    """
    FastAPI Dependency -- kiem tra vai tro cua current_user.
    Vi du: dependencies=[Depends(require_role("station_owner", "admin"))]

    Mac dinh tu choi (deny-by-default): neu route khong khai bao thi se bi chặn
    bang cach khong dua dependency nay vao.
    """
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_names = [r.name for r in current_user.roles]
        if not any(role in user_role_names for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Khong co quyen truy cap",
            )
        return current_user

    checker.__role_guard__ = True
    return checker


# Type alias cho de dang
CurrentUser = Annotated[User, Depends(get_current_user)]
