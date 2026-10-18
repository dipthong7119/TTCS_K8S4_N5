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
    SANDBOX_WEBHOOK_SECRET: str = ""
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
    REMOTE_START_WAIT: int = Field(60, ge=1)
    REMOTE_START_CALL_TIMEOUT: int = Field(30, ge=1)
    REMOTE_START_LATE_GRACE: int = Field(300, ge=0)
    REMOTE_START_ALLOWED_STATUSES: tuple[str, ...] = ("Available", "Preparing")
    SESSION_OFFLINE_GRACE_SECONDS: int = 21600
    REMOTE_STOP_REVIEW_SECONDS: int = 120
    UNKNOWN_CONNECTOR_WARN_INTERVAL: int = 300

    # S-52: đặt chỗ quá hạn không tới
    # Ân hạn trước khi job giành quyền (giây); lý do: StartTransaction bù từ trụ ngoại tuyến
    # có thể tới muộn sau expiry_at một chút — ân hạn cho phép nó còn được coi là fulfilled.
    NO_SHOW_GRACE_SECONDS: int = Field(120, ge=0)
    # Chu kỳ job quét đặt chỗ quá hạn (giây)
    RESERVATION_EXPIRY_JOB_INTERVAL: int = Field(60, ge=1)
    # Tối đa đặt chỗ xử lý mỗi lần quét
    RESERVATION_EXPIRY_BATCH: int = Field(100, ge=1)
    # Miễn phí lần đầu không đến (false = an toàn, không miễn; bật bằng env)
    NO_SHOW_FIRST_FREE: bool = False
    # Số lần thử tối đa gửi CancelReservation
    CANCEL_RESERVATION_MAX_ATTEMPTS: int = Field(5, ge=1)
    # Cửa sổ thời gian thử lại CancelReservation (giây); sau đó chuyển abandoned
    CANCEL_RESERVATION_RETRY_WINDOW: int = Field(86400, ge=60)
    # S-51: Khoảng thời gian trước expiry_at không còn được huỷ (giây). Mặc định 0 = huỷ sát giờ.
    CANCEL_CUTOFF_SECONDS: int = Field(0, ge=0)

    # S-47: Tìm trạm gần (nearby stations)
    NEARBY_DEFAULT_RADIUS_KM: float = Field(20.0, gt=0)
    NEARBY_MAX_RADIUS_KM: float = Field(100.0, gt=0)
    NEARBY_DEFAULT_LIMIT: int = Field(20, ge=1, le=50)
    NEARBY_MAX_LIMIT: int = Field(50, ge=1, le=50)
    # Múi giờ vận hành để chọn đúng khung giờ biểu giá
    STATION_TIMEZONE: str = "Asia/Ho_Chi_Minh"

    # Optional global override for SCRUM-72. If omitted, the wallet service
    # derives the floor from 5 kWh at the highest effective station tariff.
    WALLET_MINIMUM_BALANCE_VND: int | None = Field(default=None, ge=0)

    # Giới hạn nạp tiền thủ công
    MANUAL_TOPUP_MIN: int = Field(1000, ge=1)
    MANUAL_TOPUP_MAX: int = Field(20_000_000, ge=1)

    # Cảnh báo giám sát vận hành (SCRUM-90 / S-46)
    ALERT_OFFLINE_THRESHOLD_MINUTES: int = Field(15, ge=1)
    ALERT_ERROR_COUNT_THRESHOLD: int = Field(3, ge=1)
    ALERT_ERROR_WINDOW_MINUTES: int = Field(10, ge=1)

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
