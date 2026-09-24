"""
config.py — Nơi DUY NHẤT đọc biến môi trường trong toàn bộ backend.
Không rải os.environ ở bất kỳ file nào khác (quy tắc cứng từ 02_CODING_STANDARDS.md).
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    # PostgreSQL qua asyncpg — đọc từ biến môi trường DATABASE_URL
    DATABASE_URL: str = "postgresql://csms:csms@db:5432/csms"

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── App ───────────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # ── Login protection (SSD-1) ─────────────────────────────────────────────
    # Tham số cấu hình — không hardcode (quy tắc 5 trong 02_CODING_STANDARDS.md)
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
