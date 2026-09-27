"""
config.py — nơi DUY NHẤT đọc biến môi trường (02_CODING_STANDARDS.md quy tắc 1)
Tham chiếu: SPRINT_1.md mục "Biến môi trường cần thiết"
"""

import os
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
ENV_FILE = Path(os.environ.get("CSMS_ENV_FILE", ROOT_ENV_FILE))


class Settings(BaseSettings):
    # Cơ sở dữ liệu — SQLite cho dev local, PostgreSQL cho staging/production
    DATABASE_URL: str = "sqlite:///./csms.db"
    CSMS_SQLITE_PATH: str | None = None
    CSMS_DB_NAME: str = "csms"
    CSMS_DB_USER: str = "csms"
    CSMS_DB_PASSWORD: str = "csms"

    # Bảo mật
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Môi trường ứng dụng
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Bảo vệ đăng nhập (lưu vào DB không lưu RAM — SSD-1)
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    # OCPP 1.6J and background job settings
    OCPP_HEARTBEAT_INTERVAL_SECONDS: int = 300
    OCPP_HEARTBEAT_MULTIPLIER: int = 2
    OCPP_MESSAGE_RETENTION_DAYS: int = 7
    OCPP_JOB_POLL_SECONDS: int = 60
    OCPP_REMOTE_CALL_TIMEOUT_SECONDS: int = 30

    model_config = {
        "env_file": str(ENV_FILE),
        "env_file_encoding": "utf-8",
    }

    @model_validator(mode="after")
    def use_persistent_container_sqlite_path(self):
        if self.CSMS_SQLITE_PATH and self.DATABASE_URL == "sqlite:///./csms.db":
            self.DATABASE_URL = f"sqlite:///{Path(self.CSMS_SQLITE_PATH).as_posix()}"
        return self


settings = Settings()
