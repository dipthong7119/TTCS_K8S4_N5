"""
config.py — nơi DUY NHẤT đọc biến môi trường.
Tham chiếu: prompts/00_QUY_TAC_AGENT.md và bảng cấu hình trong README.md.
"""

import os
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
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
    CSMS_BACKUP_RETENTION_DAYS: int = Field(14, ge=1)

    # Compose-only options declared here so shared .env files remain valid.
    # The independent simulator receives CLI arguments, never imports Settings.
    CSMS_SIMULATOR_COUNT: int = Field(20, ge=1, le=20)
    CSMS_SIMULATOR_INCLUDE_DEMO_STATIONS: bool = False
    CSMS_SIMULATOR_URL: str = "ws://app:8000/ocpp"
    CSMS_SIMULATOR_IMAGE: str | None = None

    # Local Windows development can start its own OCPP fleet without Compose.
    CSMS_LOCAL_SIMULATOR_ENABLED: bool = False
    CSMS_LOCAL_SIMULATOR_COUNT: int = Field(20, ge=1, le=20)
    CSMS_LOCAL_SIMULATOR_INCLUDE_DEMO_STATIONS: bool = True
    CSMS_LOCAL_SIMULATOR_URL: str = "ws://127.0.0.1:8000/ocpp"

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
    OCPP_HEARTBEAT_INTERVAL_SECONDS: int = Field(
        300,
        gt=0,
        validation_alias=AliasChoices("OCPP_HEARTBEAT_INTERVAL_SECONDS", "HEARTBEAT_INTERVAL"),
    )
    OCPP_HEARTBEAT_MULTIPLIER: int = 2
    OCPP_MESSAGE_RETENTION_DAYS: int = 7
    OCPP_JOB_POLL_SECONDS: int = 60
    OCPP_REMOTE_CALL_TIMEOUT_SECONDS: int = 30
    SESSION_OFFLINE_GRACE_SECONDS: int = 21600
    REMOTE_STOP_REVIEW_SECONDS: int = 120
    UNKNOWN_CONNECTOR_WARN_INTERVAL: int = 300

    @property
    def HEARTBEAT_INTERVAL(self) -> int:
        """Keep the legacy name synchronized with the offline detection interval."""
        return self.OCPP_HEARTBEAT_INTERVAL_SECONDS

    @HEARTBEAT_INTERVAL.setter
    def HEARTBEAT_INTERVAL(self, value: int) -> None:
        self.OCPP_HEARTBEAT_INTERVAL_SECONDS = value

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
