"""
routers/auth.py -- S-02: dang nhap, khoa tam khi sai nhieu lan
Tham chieu: SPRINT_1.md T-05, SSD-1 trong 03_SSD_SPEC.md
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import deny_unannotated_route, public_route, require_role
from app.core.security import verify_password
from app.database import get_db
from app.models.login_ip_attempt import LoginIPAttempt
from app.models.user import User
from app.schemas.user import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(deny_unannotated_route)])

# Thong bao loi GIONG HET NHAU -- khong tiet lo email co ton tai hay khong (SSD-1)
_ERR_WRONG = "email hoặc mật khẩu không đúng"
_ERR_LOCKED = "tài khoản tạm khoá 15 phút"

ROLE_HOME_PAGES = {
    "driver": "/sessions/mine",
    "station_owner": "/stations",
    "operator": "/monitoring",
    "accountant": "/wallet",
    "admin": "/monitoring",
}


def role_home_page(role_names: list[str]) -> str:
    """Select the main page for a user's assigned role(s)."""
    for role in ("admin", "operator", "station_owner", "accountant", "driver"):
        if role in role_names:
            return ROLE_HOME_PAGES[role]
    raise HTTPException(status_code=403, detail="Tài khoản chưa được phân quyền")


@router.post("/login", response_model=LoginResponse)
@public_route
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Dang nhap bang email + mat khau.
    - Sai >= MAX_LOGIN_ATTEMPTS lan -> khoa LOCKOUT_DURATION_MINUTES phut (SSD-1)
    - Dem sai luu o DB, khong luu bien trong tien trinh (SSD-1 rang buoc)
    """
    user: User | None = db.query(User).filter(User.email == body.email).first()

    # --- Kiem tra khoa truoc (du mat khau co dung thi van khoa) ---
    client_ip = request.client.host if request.client else None
    
    # IP counters are separate from users; failed logins must not create fake
    # accounts in the users table.
    ip_attempt = None
    if client_ip:
        ip_attempt = (
            db.query(LoginIPAttempt)
            .filter(LoginIPAttempt.ip_address == client_ip)
            .first()
        )
        if (
            ip_attempt
            and ip_attempt.locked_until
            and ip_attempt.locked_until > datetime.now(UTC).replace(tzinfo=None)
        ):
            raise HTTPException(status_code=401, detail=_ERR_LOCKED)

    # 2. Check account lockout
    if user and user.locked_until and user.locked_until > datetime.now(UTC).replace(tzinfo=None):
        raise HTTPException(status_code=401, detail=_ERR_LOCKED)

    # --- Xac thuc ---
    ok = user is not None and user.is_active and verify_password(body.password, user.password_hash)

    if not ok:
        # Update IP tracker
        if client_ip:
            if not ip_attempt:
                ip_attempt = LoginIPAttempt(ip_address=client_ip, failed_login_count=0)
                db.add(ip_attempt)
            ip_attempt.failed_login_count = (ip_attempt.failed_login_count or 0) + 1
            if ip_attempt.failed_login_count >= settings.MAX_LOGIN_ATTEMPTS:
                ip_attempt.locked_until = datetime.now(UTC).replace(tzinfo=None) + timedelta(
                    minutes=settings.LOCKOUT_DURATION_MINUTES
                )
                
        # Update User tracker
        if user:
            # +1 so lan sai, luu IP
            user.failed_login_count = (user.failed_login_count or 0) + 1
            user.last_failed_ip = client_ip
            if user.failed_login_count >= settings.MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
                
        db.commit()
        # Tra ve cung thong bao loi (khong tiet lo email co ton tai hay khong)
        raise HTTPException(status_code=401, detail=_ERR_WRONG)

    # --- Dang nhap thanh cong: reset dem sai ---
    if ip_attempt:
        ip_attempt.failed_login_count = 0
        ip_attempt.locked_until = None
    
    user.failed_login_count = 0
    user.locked_until = None
    user.last_failed_ip = None
    db.commit()

    # Luu user_id vao session cookie (itsdangerous qua itsdangerous SessionMiddleware)
    request.session["user_id"] = user.id
    request.session["email"] = user.email

    role_names = [r.name for r in user.roles]
    redirect_to = role_home_page(role_names)

    return LoginResponse(
        message="Dang nhap thanh cong",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=role_names,
        redirect_to=redirect_to,
    )


@router.post("/logout", dependencies=[Depends(require_role("driver", "station_owner", "operator", "accountant", "admin"))])
async def logout(request: Request):
    """Xoa session, chuyen ve trang dang nhap."""
    request.session.clear()
    return {"message": "Da dang xuat"}
