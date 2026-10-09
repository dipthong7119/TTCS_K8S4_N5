"""
main.py -- Khởi tạo FastAPI app, mount router, quản lý vòng đời ứng dụng.
Tham chiếu: SPRINT_1.md S-01 T-01, 01_CODEBASE_MAP.md
"""

import asyncio
import logging
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.core.deps import deny_unannotated_route, public_route
from app.routers.audit import router as audit_router
from app.routers.auth import router as auth_router
from app.routers.charge_points import router as charge_points_router
from app.routers.charge_point_configuration import router as charge_point_configuration_router
from app.routers.monitoring import router as monitoring_router
from app.routers.ocpp import router as ocpp_router
from app.routers.pages import router as pages_router
from app.routers.reconciliation import router as reconciliation_router
from app.routers.remote import router as remote_router
from app.routers.sessions import router as sessions_router
from app.routers.stations import router as stations_router
from app.routers.wallet import router as wallet_router

logger = logging.getLogger(__name__)


async def _run_local_simulator_fleet() -> None:
    """Keep the local development fleet connected across Uvicorn reloads."""
    from app.dev_tools.ocpp_simulator.simulator import run_fleet, simulator_codes

    codes = simulator_codes(
        settings.CSMS_LOCAL_SIMULATOR_COUNT,
        include_demo_stations=settings.CSMS_LOCAL_SIMULATOR_INCLUDE_DEMO_STATIONS,
    )
    while True:
        try:
            logger.info("Starting local OCPP simulator fleet (%s charge points)", len(codes))
            await run_fleet(codes, settings.CSMS_LOCAL_SIMULATOR_URL)
            logger.warning("Local OCPP simulator fleet stopped; reconnecting in 3 seconds")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Local OCPP simulator fleet failed; retrying in 3 seconds")
        await asyncio.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Chạy Alembic 'upgrade head' khi container khởi động.
    Đảm bảo schema luôn đồng bộ trước khi nhận request đầu tiên.
    """
    backend_dir = Path(__file__).parent.parent  # thư mục backend/
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(backend_dir),
        check=True,
    )

    if settings.APP_ENV == "development":
        subprocess.run(
            [sys.executable, "seed_data.py"],
            cwd=str(backend_dir),
            check=True,
        )

    # T-26: Start background job

    from app.services.jobs import check_offline_charge_points, cleanup_old_ocpp_messages
    bg_task = asyncio.create_task(check_offline_charge_points())
    cleanup_task = asyncio.create_task(cleanup_old_ocpp_messages())
    local_simulator_task: asyncio.Task[None] | None = None
    if settings.APP_ENV == "development" and settings.CSMS_LOCAL_SIMULATOR_ENABLED:
        local_simulator_task = asyncio.create_task(_run_local_simulator_fleet())

    yield

    bg_task.cancel()
    cleanup_task.cancel()
    tasks = [bg_task, cleanup_task]
    if local_simulator_task is not None:
        local_simulator_task.cancel()
        tasks.append(local_simulator_task)
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(
    title="CSMS - Nền tảng vận hành trạm sạc xe điện",
    description="Hệ thống quản lý trụ sạc và giao tiếp OCPP",
    version="1.0.0",
    lifespan=lifespan,
    dependencies=[Depends(deny_unannotated_route)],
)

# -- Session cookie (httpOnly, SameSite=lax) ---------------------------------
# SECRET_KEY đọc từ config.py -- không hardcode (02_CODING_STANDARDS.md quy tắc 1)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="csms_session",
    max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    same_site="lax",
    https_only=False,  # đổi thành True khi deploy HTTPS
)

# -- Static files (CSS, JS, ảnh) -------------------------------------------
# Volume mount: ./frontend:/app/frontend (từ docker-compose.yml)
docker_frontend_dir = Path("/app/frontend")

if docker_frontend_dir.exists():
    frontend_dir = docker_frontend_dir
else:
    frontend_dir = Path(__file__).parent.parent.parent / "frontend"

app.mount("/static", StaticFiles(directory=str(frontend_dir / "static")), name="static")

# -- Templates (Jinja2) -------------------------------------------------------
_templates_dir = frontend_dir / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

# -- Routers ------------------------------------------------------------------
app.include_router(auth_router, prefix="/api")
app.include_router(stations_router, prefix="/api")
app.include_router(charge_points_router, prefix="/api")
app.include_router(charge_point_configuration_router, prefix="/api")
app.include_router(monitoring_router, prefix="/api/monitoring")
app.include_router(ocpp_router)
app.include_router(remote_router, prefix="/api")
app.include_router(sessions_router, prefix="/api")
app.include_router(reconciliation_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(wallet_router, prefix="/api")

app.include_router(pages_router)

# -- Health check -------------------------------------------------------------
@app.get("/health")
@public_route
async def health_check():
    """API kiểm tra sức khỏe hệ thống (Health Check) -- dùng cho Docker/Load Balancer"""
    return {"status": "ok", "message": "Hệ thống đang hoạt động ổn định"}
