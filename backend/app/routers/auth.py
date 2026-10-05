"""
routers/auth.py -- S-02: dang nhap, khoa tam khi sai nhieu lan
Tham chieu: SPRINT_1.md T-05, SSD-1 trong 03_SSD_SPEC.md
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import CurrentUser, deny_unannotated_route, public_route, require_role
from app.core.security import verify_password
from app.database import get_db
from app.models.login_ip_attempt import LoginIPAttempt
from app.models.user import User
from app.schemas.user import LoginRequest, LoginResponse, MeResponse

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


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"description": "Thông tin đăng nhập sai hoặc tài khoản/địa chỉ IP đang bị khóa"},
        403: {"description": "Tài khoản chưa được phân quyền"},
    },
)
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
    now = datetime.now(UTC).replace(tzinfo=None)
    user: User | None = db.query(User).filter(User.email == body.email).first()
    client_ip = request.client.host if request.client else None
    ip_attempt = None
    if client_ip:
        ip_attempt = (
            db.query(LoginIPAttempt)
            .filter(LoginIPAttempt.ip_address == client_ip)
            .first()
        )

    # Check account and IP lockouts before verifying the password. Expired
    # windows start a fresh consecutive-failure count.
    for tracker in (user, ip_attempt):
        if tracker and tracker.locked_until:
            if tracker.locked_until > now:
                raise HTTPException(status_code=401, detail=_ERR_LOCKED)
            tracker.failed_login_count = 0
            tracker.locked_until = None

    # --- Xac thuc ---
    ok = user is not None and user.is_active and verify_password(body.password, user.password_hash)

    if not ok:
        # Track failures by IP even for unknown emails, without creating fake users.
        if client_ip:
            if ip_attempt is None:
                ip_attempt = LoginIPAttempt(ip_address=client_ip, failed_login_count=0)
                db.add(ip_attempt)
            ip_attempt.failed_login_count = (ip_attempt.failed_login_count or 0) + 1
            if ip_attempt.failed_login_count >= settings.MAX_LOGIN_ATTEMPTS:
                ip_attempt.locked_until = now + timedelta(
                    minutes=settings.LOCKOUT_DURATION_MINUTES
                )

        # Also track failures against a known account.
        if user:
            user.failed_login_count = (user.failed_login_count or 0) + 1
            user.last_failed_ip = client_ip
            if user.failed_login_count >= settings.MAX_LOGIN_ATTEMPTS:
                user.locked_until = now + timedelta(
                    minutes=settings.LOCKOUT_DURATION_MINUTES
                )

        if user or ip_attempt:
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


# Nhan hien thi tieng Viet theo do uu tien vai tro
_ROLE_LABEL_MAP = {
    "admin":         "Quản trị viên",
    "operator":      "Vận hành viên",
    "station_owner": "Chủ trạm",
    "accountant":    "Kế toán",
    "driver":        "Tài xế",
}
_ROLE_PRIORITY = ["admin", "operator", "station_owner", "accountant", "driver"]


@router.get("/me", response_model=MeResponse,
            dependencies=[Depends(require_role(
                "admin", "operator", "station_owner", "accountant", "driver"
            ))])
async def get_me(current_user: CurrentUser):
    """
    Tra ve thong tin nguoi dung dang dang nhap.
    Duoc goi boi route_guard.js (SCRUM-135) de kiem tra phien va quyen.
    """
    role_names = [r.name for r in current_user.roles]
    # Lay nhan cua role co uu tien cao nhat
    main_role = next(
        (r for r in _ROLE_PRIORITY if r in role_names),
        role_names[0] if role_names else "unknown",
    )
    return MeResponse(
        user_id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name or "",
        roles=role_names,
        role_label=_ROLE_LABEL_MAP.get(main_role, main_role),
    )
