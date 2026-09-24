from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import settings
from app.routers.pages import router as pages_router

app = FastAPI(
    title="CSMS - Nền tảng vận hành trạm sạc xe điện",
    description="Hệ thống quản lý trụ sạc và giao tiếp OCPP",
    version="1.0.0"
)

# ── Static files (CSS, JS, ảnh) ───────────────────────────────────
# Volume mount: ./frontend:/app/frontend (từ docker-compose.yml)
# Sử dụng đường dẫn tuyệt đối /app/frontend vì volume mount này luôn tồn tại khi container chạy
frontend_dir = Path("/app/frontend")
app.mount("/static", StaticFiles(directory=str(frontend_dir / "static")), name="static")

# ── Templates (Jinja2) ─────────────────────────────────────────────
# Cùng đường mount trên
templates = Jinja2Templates(directory=str(frontend_dir / "templates"))

# ── Routers ────────────────────────────────────────────────────────
app.include_router(pages_router)

# ── Health check ───────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """API kiểm tra sức khoẻ hệ thống (Health Check) — dùng cho Docker/Load Balancer"""
    return {"status": "ok", "message": "Hệ thống đang hoạt động ổn định"}