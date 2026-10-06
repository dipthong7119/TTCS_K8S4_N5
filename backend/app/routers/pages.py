from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, public_route, require_role
from app.database import get_db
from app.models.charge_point import ChargePoint
from app.services.ownership import get_station_for_user

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


@router.get("/monitoring", dependencies=[Depends(require_role("admin", "operator", "station_owner"))])
async def monitoring_page(request: Request, current_user: CurrentUser):
    roles = _require_any_role(current_user, "admin", "operator", "station_owner")
    return templates.TemplateResponse(
        request,
        "monitoring/grid.html",
        _page_context(
            request,
            current_user,
            can_reset=bool({"admin", "operator"}.intersection(roles)),
        ),
    )


@router.get("/stations", dependencies=[Depends(require_role("admin", "station_owner", "operator"))])
async def stations_page(request: Request, current_user: CurrentUser):
    roles = _require_any_role(current_user, "admin", "station_owner", "operator")
    return templates.TemplateResponse(
        request,
        "stations/list.html",
        _page_context(
            request,
            current_user,
            can_manage_stations=bool({"admin", "station_owner"}.intersection(roles)),
            can_lock_stations="admin" in roles,
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
