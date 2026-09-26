"""
hardware/config.py — Cấu hình phần cứng trạm sạc (CSMS)
Tham chieu: SPRINT_1.md K-01, 02_CODING_STANDARDS.md

Nguồn sự thật duy nhất cho cấu hình hardware.
Đọc từ biến môi trường hoặc dùng giá trị mặc định.
Không hardcode thông tin kết nối ở nơi khác.
"""

import os
from dataclasses import dataclass, field


@dataclass
class HardwareConfig:
    """
    Cấu hình đầy đủ cho hardware module.
    Ưu tiên đọc từ biến môi trường, fallback về giá trị mặc định.

    Biến môi trường hỗ trợ:
        CSMS_BACKEND_HOST       Host backend (mặc định: localhost)
        CSMS_BACKEND_PORT       Port backend (mặc định: 8000)
        CSMS_CP_CODE            Mã trụ sạc (mặc định: CP-TEST-01)
        CSMS_HEARTBEAT_INTERVAL Chu kỳ heartbeat giây (mặc định: 10)
        CSMS_WS_TIMEOUT         Timeout WebSocket giây (mặc định: 5)
        CSMS_HTTP_TIMEOUT       Timeout HTTP giây (mặc định: 5)
        CSMS_LOG_LEVEL          Mức log (mặc định: INFO)
    """

    # Backend
    backend_host: str = field(
        default_factory=lambda: os.getenv("CSMS_BACKEND_HOST", "localhost")
    )
    backend_port: int = field(
        default_factory=lambda: int(os.getenv("CSMS_BACKEND_PORT", "8000"))
    )

    # Trụ sạc
    charge_point_code: str = field(
        default_factory=lambda: os.getenv("CSMS_CP_CODE", "CP-TEST-01")
    )
    heartbeat_interval: int = field(
        default_factory=lambda: int(os.getenv("CSMS_HEARTBEAT_INTERVAL", "10"))
    )

    # Kết nối
    ws_timeout: float = field(
        default_factory=lambda: float(os.getenv("CSMS_WS_TIMEOUT", "5"))
    )
    http_timeout: float = field(
        default_factory=lambda: float(os.getenv("CSMS_HTTP_TIMEOUT", "5"))
    )

    # Logging
    log_level: str = field(
        default_factory=lambda: os.getenv("CSMS_LOG_LEVEL", "INFO").upper()
    )

    # ---------------------------------------------------------------------------
    # Computed properties
    # ---------------------------------------------------------------------------

    @property
    def backend_url(self) -> str:
        """URL HTTP đầy đủ của backend."""
        return f"http://{self.backend_host}:{self.backend_port}"

    @property
    def ws_url(self) -> str:
        """URL WebSocket OCPP của trụ sạc."""
        return f"ws://{self.backend_host}:{self.backend_port}/ocpp/{self.charge_point_code}"

    @property
    def health_url(self) -> str:
        """URL endpoint health check."""
        return f"{self.backend_url}/health"

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def display(self) -> None:
        """In cấu hình hiện tại ra stdout (không log secret)."""
        print("─" * 45)
        print("  CSMS Hardware Config")
        print("─" * 45)
        print(f"  backend_url       : {self.backend_url}")
        print(f"  ws_url            : {self.ws_url}")
        print(f"  charge_point_code : {self.charge_point_code}")
        print(f"  heartbeat_interval: {self.heartbeat_interval}s")
        print(f"  ws_timeout        : {self.ws_timeout}s")
        print(f"  http_timeout      : {self.http_timeout}s")
        print(f"  log_level         : {self.log_level}")
        print("─" * 45)

    @classmethod
    def from_env(cls) -> "HardwareConfig":
        """Tạo cấu hình từ biến môi trường (factory method rõ ràng hơn)."""
        return cls()


# Singleton dùng chung toàn module (import từ đây thay vì khởi tạo lại)
default_config = HardwareConfig()
