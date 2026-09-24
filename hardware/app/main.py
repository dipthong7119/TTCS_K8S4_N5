from fastapi import FastAPI
import logging

app = FastAPI(
    title="CSMS - Nền tảng vận hành trạm sạc xe điện",
    description="Hệ thống quản lý trụ sạc và giao tiếp OCPP",
    version="1.0.0"
)

@app.get("/health")
async def health_check():
    """
    API kiểm tra sức khoẻ hệ thống (Health Check)
    Dùng cho CI/CD và Docker Compose kiểm tra trạng thái
    """
    return {"status": "ok", "message": "Hệ thống đang hoạt động ổn định"}
