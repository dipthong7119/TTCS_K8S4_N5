from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, public_route, require_role
from app.database import get_db
from app.models.charge_point import ChargePoint
from app.models.station import Station
from app.services.ownership import filter_by_owner, get_station_for_user

router = APIRouter()

# Volume mount: ./frontend:/app/frontend (từ docker-compose.yml)
docker_frontend_dir = Path("/app/frontend")
if docker_frontend_dir.exists():
    _templates_dir = docker_frontend_dir / "templates"
else:
    _templates_dir = Path(__file__).parent.parent.parent.parent / "frontend" / "templates"

templates = Jinja2Templates(directory=str(_templates_dir))


def asset_url(asset_path: str) -> str:
    """Change JS/CSS URLs when files change so cached scripts stay in sync with HTML."""
    asset_stat = (_templates_dir.parent / "static" / asset_path).stat()
    version = f"{asset_stat.st_mtime_ns:x}-{asset_stat.st_size:x}"
    return f"/static/{asset_path}?v={version}"


templates.env.globals["asset_url"] = asset_url

ROLE_LABELS = {
    "driver": "Tài xế",
    "station_owner": "Chủ trạm",
    "operator": "Vận hành viên",
    "accountant": "Kế toán",
    "admin": "Quản trị viên",
}


def _require_any_role(current_user, *allowed_roles: str) -> list[str]:
    roles = [role.name for role in current_user.roles]
    if not set(roles).intersection(allowed_roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập")
    return roles


def _page_context(request: Request, current_user, **extra):
    roles = [role.name for role in current_user.roles]
    display_roles = [ROLE_LABELS.get(role, role) for role in roles]
    name_parts = current_user.full_name.split()
    initials = "".join(part[0] for part in name_parts[:2]).upper()
    return {
        "request": request,
        "current_user": {
            "id": current_user.id,
            "name": current_user.full_name,
            "role": ", ".join(display_roles),
            "roles": roles,
            "initials": initials or "?",
        },
        **extra,
    }


@router.get("/")
@public_route
async def root():
    """Redirect trang chủ tới trang đăng nhập."""
    return RedirectResponse(url="/login", status_code=302)


@router.get("/login")
@public_route
async def login_page(request: Request):
    """Trang đăng nhập độc lập."""
    return templates.TemplateResponse(request, "auth/login.html", {"request": request})


@router.get("/logout")
@public_route
async def logout_get(request: Request):
    return RedirectResponse(url="/login", status_code=302)


@router.post("/auth/logout")
@public_route
async def logout_post(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@router.get("/monitoring", dependencies=[Depends(require_role("admin", "operator", "station_owner", "driver"))])
async def monitoring_page(request: Request, current_user: CurrentUser):
    roles = _require_any_role(current_user, "admin", "operator", "station_owner", "driver")
    return templates.TemplateResponse(
        request,
        "monitoring/grid.html",
        _page_context(
            request,
            current_user,
            can_reset=bool({"admin", "operator"}.intersection(roles)),
        ),
    )


@router.get("/stations", dependencies=[Depends(require_role("admin", "station_owner", "operator", "driver"))])
async def stations_page(request: Request, current_user: CurrentUser):
    roles = _require_any_role(current_user, "admin", "station_owner", "operator", "driver")
    driver_directory = "driver" in roles and not {
        "admin", "station_owner", "operator"
    }.intersection(roles)
    if driver_directory:
        roles = ["driver"]
    return templates.TemplateResponse(
        request,
        "stations/list.html",
        _page_context(
            request,
            current_user,
            can_manage_stations=bool({"admin", "station_owner"}.intersection(roles)),
            can_lock_stations="admin" in roles,
            is_driver_view=driver_directory,
        ),
    )


@router.get("/stations/new", dependencies=[Depends(require_role("admin", "station_owner"))])
async def new_station_page(request: Request, current_user: CurrentUser):
    _require_any_role(current_user, "admin", "station_owner")
    return templates.TemplateResponse(
        request,
        "stations/form.html",
        _page_context(
            request,
            current_user,
            can_manage_stations=True,
            can_lock_stations="admin" in [role.name for role in current_user.roles],
        ),
    )


@router.get("/stations/revenue", dependencies=[Depends(require_role("admin", "station_owner"))])
async def station_revenue_page(
    request: Request,
    current_user: CurrentUser,
    station_id: int | None = None,
    db: Session = Depends(get_db),
):
    roles = _require_any_role(current_user, "admin", "station_owner")
    q = filter_by_owner(db.query(Station), current_user.id, roles)
    stations = q.order_by(Station.name.asc()).all()
    return templates.TemplateResponse(
        request,
        "stations/revenue.html",
        _page_context(
            request,
            current_user,
            stations=stations,
            selected_station_id=station_id,
        ),
    )


@router.get("/stations/{station_id}/edit", dependencies=[Depends(require_role("admin", "station_owner"))])
async def edit_station_page(
    request: Request,
    station_id: int,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    roles = _require_any_role(current_user, "station_owner", "admin")
    station = get_station_for_user(db, station_id, current_user.id, roles, "edit_page")
    charge_points = (
        db.query(ChargePoint)
        .filter(ChargePoint.station_id == station.id)
        .order_by(ChargePoint.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "stations/form.html",
        _page_context(
            request,
            current_user,
            station=station,
            charge_points=charge_points,
            can_manage_stations=True,
            can_lock_stations="admin" in roles,
        ),
    )


@router.get("/tariffs", dependencies=[Depends(require_role("admin", "station_owner"))])
async def tariffs_page():
    """Redirect to station management where station tariffs are configured."""
    return RedirectResponse(url="/stations", status_code=status.HTTP_302_FOUND)


@router.get("/sessions", dependencies=[Depends(require_role("admin", "operator", "accountant", "station_owner"))])
async def sessions_page(request: Request, current_user: CurrentUser):
    roles = _require_any_role(current_user, "admin", "operator", "accountant", "station_owner")
    return templates.TemplateResponse(
        request,
        "sessions/my_session.html",
        _page_context(
            request,
            current_user,
            is_global_sessions=True,
            show_driver_column=True,
            can_view_all_sessions=bool({"admin", "operator", "accountant"}.intersection(roles)),
            can_subscribe_sessions=bool({"admin", "operator", "station_owner", "driver"}.intersection(roles)),
            can_remote_stop=bool({"admin", "operator"}.intersection(roles)),
        ),
    )


@router.get("/sessions/mine", dependencies=[Depends(require_role("driver"))])
async def my_sessions_page(request: Request, current_user: CurrentUser):
    _require_any_role(current_user, "driver")
    return templates.TemplateResponse(
        request,
        "sessions/my_session.html",
        _page_context(
            request,
            current_user,
            is_global_sessions=False,
            show_driver_column=False,
            can_view_all_sessions=False,
            can_subscribe_sessions=True,
            can_remote_stop=False,
        ),
    )


@router.get("/sessions/anomalies", dependencies=[Depends(require_role("admin", "operator"))])
async def anomalies_page(request: Request, current_user: CurrentUser):
    _require_any_role(current_user, "admin", "operator")
    return templates.TemplateResponse(
        request, "sessions/anomaly_list.html", _page_context(request, current_user)
    )


# SCRUM-184 — Xuất bảng đối chiếu kWh (Phạm Văn Tuấn)
@router.get("/sessions/kwh-reconciliation", dependencies=[Depends(require_role("admin", "operator"))])
async def kwh_reconciliation_page(request: Request, current_user: CurrentUser):
    _require_any_role(current_user, "admin", "operator")
    return templates.TemplateResponse(
        request, "sessions/kwh_reconciliation.html", _page_context(request, current_user)
    )


@router.get("/audit", dependencies=[Depends(require_role("admin", "operator"))])
async def audit_page(request: Request, current_user: CurrentUser):
    _require_any_role(current_user, "admin", "operator")
    return templates.TemplateResponse(
        request, "sessions/audit.html", _page_context(request, current_user)
    )


@router.get("/wallet", dependencies=[Depends(require_role("admin", "accountant", "driver"))])
async def wallet_page(request: Request, current_user: CurrentUser):
    roles = _require_any_role(current_user, "admin", "accountant", "driver")
    template_name = "wallet/admin_drivers.html" if "admin" in roles or "accountant" in roles else "wallet/wallet.html"
    return templates.TemplateResponse(
        request, template_name, _page_context(request, current_user)
    )


@router.get("/wallet/sandbox-checkout", dependencies=[Depends(require_role("driver"))])
async def sandbox_checkout_page(request: Request, current_user: CurrentUser, order_code: str = ""):
    _require_any_role(current_user, "driver")
    return templates.TemplateResponse(
        request,
        "wallet/sandbox_checkout.html",
        _page_context(request, current_user, order_code=order_code),
    )


# SCRUM-231 / SCRUM-85 — Giao diện đối soát cho kế toán
@router.get(
    "/sessions/financial-reconciliation",
    dependencies=[Depends(require_role("admin", "accountant", "station_owner"))],
)
async def financial_reconciliation_page(
    request: Request,
    current_user: CurrentUser,
):
    roles = _require_any_role(current_user, "admin", "accountant", "station_owner")
    return templates.TemplateResponse(
        request,
        "sessions/financial_reconciliation.html",
        _page_context(
            request,
            current_user,
            can_reopen_period="admin" in roles,
        ),
    )


# SCRUM-254 / SCRUM-86 — Giao diện chia doanh thu cho đối tác (kế toán)
@router.get(
    "/sessions/revenue-sharing",
    dependencies=[Depends(require_role("admin", "accountant"))],
)
async def revenue_sharing_page(
    request: Request,
    current_user: CurrentUser,
):
    _require_any_role(current_user, "admin", "accountant")
    return templates.TemplateResponse(
        request,
        "sessions/revenue_sharing.html",
        _page_context(request, current_user),
    )


# SCRUM-68 — Giao diện đăng ký gói thuê bao hàng tháng (Phạm Văn Tuấn)
@router.get("/subscriptions", dependencies=[Depends(require_role("driver", "admin"))])
async def subscriptions_page(request: Request, current_user: CurrentUser):
    _require_any_role(current_user, "driver", "admin")
    return templates.TemplateResponse(
        request, "subscriptions/subscriptions.html", _page_context(request, current_user)
    )


# SCRUM-76 — Màn hình đặt chỗ trụ sạc cho tài xế (Phạm Văn Tuấn)
@router.get("/reservations", dependencies=[Depends(require_role("driver", "admin", "operator"))])
async def reservations_page(request: Request, current_user: CurrentUser):
    _require_any_role(current_user, "driver", "admin", "operator")
    return templates.TemplateResponse(
        request, "reservations/list.html", _page_context(request, current_user)
    )



# SCRUM-90 — Cảnh báo vận hành (Phạm Văn Tuấn)
@router.get("/monitoring/alerts", dependencies=[Depends(require_role("admin", "operator"))])
async def monitoring_alerts_page(request: Request, current_user: CurrentUser):
    _require_any_role(current_user, "admin", "operator")
    return templates.TemplateResponse(
        request, "monitoring/alerts.html", _page_context(request, current_user)
    )


# SCRUM-91 — Nhật ký thao tác ví (Phạm Văn Tuấn)
@router.get("/wallet/audit", dependencies=[Depends(require_role("admin", "operator", "accountant"))])
async def wallet_audit_page(request: Request, current_user: CurrentUser):
    _require_any_role(current_user, "admin", "operator", "accountant")
    return templates.TemplateResponse(
        request, "wallet/wallet_audit.html", _page_context(request, current_user)
    )


# SCRUM-92 — Quyền riêng tư & Yêu cầu xóa dữ liệu cá nhân (Phạm Văn Tuấn)
@router.get("/privacy", dependencies=[Depends(require_role("driver", "admin", "operator"))])
async def privacy_page(request: Request, current_user: CurrentUser):
    _require_any_role(current_user, "driver", "admin", "operator")
    return templates.TemplateResponse(
        request, "privacy/privacy.html", _page_context(request, current_user)
    )



# SCRUM-96 (FE) — Tài xế tìm trạm gần & xem đầu nối rảnh (Vy Hoàng Tú)
@router.get("/driver/stations", dependencies=[Depends(require_role("driver"))])
async def driver_station_finder_page(request: Request, current_user: CurrentUser):
    """Trang tìm trạm sạc gần đây cho tài xế — hiện trạng thái đầu nối realtime (SCRUM-96, SCRUM-241, SCRUM-242)."""
    _require_any_role(current_user, "driver")
    return templates.TemplateResponse(
        request,
        "driver/station_finder.html",
        _page_context(request, current_user),
    )


# SCRUM-98 (FE) — Theo dõi phiên sạc đang chạy & nhận thông báo khi kết thúc (Vy Hoàng Tú)
@router.get("/driver/session", dependencies=[Depends(require_role("driver"))])
async def driver_session_page(request: Request, current_user: CurrentUser):
    """Trang theo dõi phiên sạc đang chạy của tài xế với SSE realtime (SCRUM-98)."""
    _require_any_role(current_user, "driver")
    return templates.TemplateResponse(
        request,
        "driver/driver_session.html",
        _page_context(request, current_user),
    )

