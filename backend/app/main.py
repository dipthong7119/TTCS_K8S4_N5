"""
main.py -- Khoi tao FastAPI app, mount router, quan ly vong doi ung dung.
Tham chieu: SPRINT_1.md S-01 T-01, 01_CODEBASE_MAP.md
"""

import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.routers.auth import router as auth_router
from app.routers.pages import router as pages_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Chay Alembic 'upgrade head' khi container khoi dong.
    Dam bao schema luon dong bo truoc khi nhan request dau tien.
    """
    backend_dir = Path(__file__).parent.parent  # thu muc backend/
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(backend_dir),
        check=True,
    )
    yield


app = FastAPI(
    title="CSMS - Nen tang van hanh tram sac xe dien",
    description="He thong quan ly tru sac va giao tiep OCPP",
    version="1.0.0",
    lifespan=lifespan,
)

# -- Session cookie (httpOnly, SameSite=lax) ---------------------------------
# SECRET_KEY doc tu config.py -- khong hardcode (02_CODING_STANDARDS.md quy tac 1)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="csms_session",
    max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    same_site="lax",
    https_only=False,  # doi thanh True khi deploy HTTPS
)

# -- Static files (CSS, JS, anh) -------------------------------------------
# Volume mount: ./frontend:/app/frontend (tu docker-compose.yml)
# Chi mount khi thu muc ton tai (trong Docker). Khi chay pytest CI thi bo qua.
frontend_dir = Path("/app/frontend")

if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir / "static")), name="static")

# -- Templates (Jinja2) -------------------------------------------------------
_templates_dir = frontend_dir / "templates" if frontend_dir.exists() else Path(__file__).parent
templates = Jinja2Templates(directory=str(_templates_dir))

# -- Routers ------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(pages_router)

# -- Health check -------------------------------------------------------------
@app.get("/health")
async def health_check():
    """API kiem tra suc khoe he thong (Health Check) -- dung cho Docker/Load Balancer"""
    return {"status": "ok", "message": "He thong dang hoat dong on dinh"}