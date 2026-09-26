"""
routers/auth.py -- S-02: dang nhap, khoa tam khi sai nhieu lan
Tham chieu: SPRINT_1.md T-05, SSD-1 trong 03_SSD_SPEC.md
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.user import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# Thong bao loi GIONG HET NHAU -- khong tiet lo email co ton tai hay khong (SSD-1)
_ERR_WRONG = "email hoặc mật khẩu không đúng"
_ERR_LOCKED = "tài khoản tạm khoá 15 phút"


@router.post("/login", response_model=LoginResponse)
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
    
    # 1. Check IP lockout first
    ip_user = None
    if client_ip:
        ip_user_email = f"ip:{client_ip}"
        ip_user = db.query(User).filter(User.email == ip_user_email).first()
        if ip_user and ip_user.locked_until and ip_user.locked_until > datetime.utcnow():
            raise HTTPException(status_code=401, detail=_ERR_LOCKED)

    # 2. Check account lockout
    if user and user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(status_code=401, detail=_ERR_LOCKED)

    # --- Xac thuc ---
    ok = user is not None and user.is_active and verify_password(body.password, user.password_hash)

    if not ok:
        # Update IP tracker
        if client_ip:
            if not ip_user:
                ip_user = User(email=ip_user_email, password_hash="", full_name="IP Tracker", is_active=False, failed_login_count=0)
                db.add(ip_user)
            ip_user.failed_login_count = (ip_user.failed_login_count or 0) + 1
            if ip_user.failed_login_count >= settings.MAX_LOGIN_ATTEMPTS:
                ip_user.locked_until = datetime.utcnow() + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
                
        # Update User tracker
        if user:
            # +1 so lan sai, luu IP
            user.failed_login_count = (user.failed_login_count or 0) + 1
            user.last_failed_ip = client_ip
            if user.failed_login_count >= settings.MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=settings.LOCKOUT_DURATION_MINUTES)
                
        db.commit()
        # Tra ve cung thong bao loi (khong tiet lo email co ton tai hay khong)
        raise HTTPException(status_code=401, detail=_ERR_WRONG)

    # --- Dang nhap thanh cong: reset dem sai ---
    if ip_user:
        ip_user.failed_login_count = 0
        ip_user.locked_until = None
    
    user.failed_login_count = 0
    user.locked_until = None
    user.last_failed_ip = None
    db.commit()

    # Luu user_id vao session cookie (itsdangerous qua itsdangerous SessionMiddleware)
    request.session["user_id"] = user.id
    request.session["email"] = user.email

    role_names = [r.name for r in user.roles]

    return LoginResponse(
        message="Dang nhap thanh cong",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=role_names,
    )


@router.post("/logout")
async def logout(request: Request):
    """Xoa session, chuyen ve trang dang nhap."""
    request.session.clear()
    return {"message": "Da dang xuat"}
