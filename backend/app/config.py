"""
config.py — nơi DUY NHẤT đọc biến môi trường (02_CODING_STANDARDS.md quy tắc 1)
Tham chiếu: SPRINT_1.md mục "Biến môi trường cần thiết"
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Cơ sở dữ liệu — SQLite cho dev local, PostgreSQL cho staging/production
    DATABASE_URL: str = "sqlite:///./csms.db"

    # Bảo mật
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Môi trường ứng dụng
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Bảo vệ đăng nhập (lưu vào DB không lưu RAM — SSD-1)
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
