from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

# Volume mount: ./frontend:/app/frontend (từ docker-compose.yml)
frontend_dir = Path("/app/frontend")
templates = Jinja2Templates(directory=str(frontend_dir / "templates"))

def _user():
    """Default user context cho sidebar — sẽ được thay bằng auth thật sau"""
    return {"name": "Người dùng", "role": "Chủ trạm", "initials": "ND"}

@router.get("/")
async def root():
    """Redirect trang chủ tới /monitoring"""
    return RedirectResponse(url="/monitoring", status_code=302)

@router.get("/login")
async def login_page(request: Request):
    """Trang đăng nhập (standalone template, không extends base.html)"""
    return templates.TemplateResponse(request, "auth/login.html", {"request": request})

@router.get("/logout")
async def logout_get(request: Request):
    """GET /logout — redirect về login (để handle trường hợp người dùng truy cập trực tiếp)"""
    return RedirectResponse(url="/login", status_code=302)

@router.post("/auth/logout")
async def logout_post():
    """POST /auth/logout — từ form trong base.html, sau khi logout về trang login"""
    return RedirectResponse(url="/login", status_code=302)

@router.get("/monitoring")
async def monitoring_page(request: Request):
    """Trang giám sát thời gian thực"""
    return templates.TemplateResponse(request, "monitoring/grid.html", {
        "request": request,
        "current_user": _user()
    })

@router.get("/stations")
async def stations_page(request: Request):
    """Trang danh sách trạm"""
    return templates.TemplateResponse(request, "stations/list.html", {
        "request": request,
        "current_user": _user()
    })

@router.get("/stations/new")
async def new_station_page(request: Request):
    """Trang tạo mới trạm"""
    return templates.TemplateResponse(request, "stations/form.html", {
        "request": request,
        "current_user": _user()
    })

@router.get("/stations/{station_id}/edit")
async def edit_station_page(request: Request, station_id: int):
    """Trang sửa trạm"""
    return templates.TemplateResponse(request, "stations/form.html", {
        "request": request,
        "current_user": _user()
    })

@router.get("/sessions")
async def sessions_page(request: Request):
    """Trang lịch sử sạc (mặc định là lịch sử cá nhân)"""
    return templates.TemplateResponse(request, "sessions/my_session.html", {
        "request": request,
        "current_user": _user()
    })

@router.get("/sessions/mine")
async def my_sessions_page(request: Request):
    """Trang lịch sử sạc của tôi"""
    return templates.TemplateResponse(request, "sessions/my_session.html", {
        "request": request,
        "current_user": _user()
    })

@router.get("/sessions/anomalies")
async def anomalies_page(request: Request):
    """Trang phiên bất thường"""
    return templates.TemplateResponse(request, "sessions/anomaly_list.html", {
        "request": request,
        "current_user": _user()
    })

@router.get("/wallet")
async def wallet_page(request: Request):
    """Trang ví điện tử"""
    return templates.TemplateResponse(request, "wallet/wallet.html", {
        "request": request,
        "current_user": _user()
    })