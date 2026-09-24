from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.routers.pages import router as pages_router

app = FastAPI(
    title="CSMS - Nền tảng vận hành trạm sạc xe điện",
    description="Hệ thống quản lý trụ sạc và giao tiếp OCPP",
    version="1.0.0"
)

# ── Static files (CSS, JS, ảnh) ───────────────────────────────────
# Volume mount: ./frontend:/app/frontend (từ docker-compose.yml)
# Chỉ mount khi thư mục tồn tại (trong Docker). Khi chạy pytest CI thì bỏ qua.
frontend_dir = Path("/app/frontend")

if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir / "static")), name="static")

# ── Templates (Jinja2) ─────────────────────────────────────────────
# Cùng đường mount trên — dùng fallback path nếu không có volume mount
_templates_dir = frontend_dir / "templates" if frontend_dir.exists() else Path(__file__).parent
templates = Jinja2Templates(directory=str(_templates_dir))

# ── Routers ────────────────────────────────────────────────────────
app.include_router(pages_router)

# ── Health check ───────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """API kiểm tra sức khoẻ hệ thống (Health Check) — dùng cho Docker/Load Balancer"""
    return {"status": "ok", "message": "Hệ thống đang hoạt động ổn định"}