"""
hardware/test_hardware.py — Unit & Integration test cho hardware module
Tham chieu: SPRINT_1.md K-01, 02_CODING_STANDARDS.md, 01_CODEBASE_MAP.md

Test bao gồm:
  - Unit: HardwareConfig, make_call, print_info
  - Integration (mock): OcppSimulator, HardwareHealthChecker
"""

import asyncio
import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Import module cần test
# ---------------------------------------------------------------------------
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from hardware.config import HardwareConfig
from hardware.hardware import (
    OcppSimulator,
    HardwareHealthChecker,
    _make_call,
    _now_iso,
    print_info,
    VENDOR,
    MODEL,
)


# ===========================================================================
# Unit Tests — HardwareConfig
# ===========================================================================

class TestHardwareConfig:
    """Kiểm tra cấu hình đọc từ giá trị mặc định và biến môi trường."""

    def test_default_values(self):
        """Giá trị mặc định khớp với spec."""
        cfg = HardwareConfig()
        assert cfg.backend_host == "localhost"
        assert cfg.backend_port == 8000
        assert cfg.charge_point_code == "CP-TEST-01"
        assert cfg.heartbeat_interval == 10
        assert cfg.log_level == "INFO"

    def test_computed_backend_url(self):
        """backend_url ghép đúng host và port."""
        cfg = HardwareConfig(backend_host="192.168.1.1", backend_port=9000)
        assert cfg.backend_url == "http://192.168.1.1:9000"

    def test_computed_ws_url(self):
        """ws_url dùng đúng mã trụ sạc."""
        cfg = HardwareConfig(charge_point_code="CP-CUSTOM-99")
        assert cfg.ws_url.endswith("/ocpp/CP-CUSTOM-99")
        assert cfg.ws_url.startswith("ws://")

    def test_computed_health_url(self):
        """health_url trỏ đúng endpoint /health."""
        cfg = HardwareConfig()
        assert cfg.health_url == "http://localhost:8000/health"

    def test_from_env_reads_environment_variables(self, monkeypatch):
        """from_env() đọc đúng biến môi trường."""
        monkeypatch.setenv("CSMS_BACKEND_HOST", "staging.example.com")
        monkeypatch.setenv("CSMS_BACKEND_PORT", "443")
        monkeypatch.setenv("CSMS_CP_CODE", "CP-STAGING-01")
        monkeypatch.setenv("CSMS_HEARTBEAT_INTERVAL", "30")
        monkeypatch.setenv("CSMS_LOG_LEVEL", "debug")

        cfg = HardwareConfig.from_env()
        assert cfg.backend_host == "staging.example.com"
        assert cfg.backend_port == 443
        assert cfg.charge_point_code == "CP-STAGING-01"
        assert cfg.heartbeat_interval == 30
        assert cfg.log_level == "DEBUG"  # phải uppercase

    def test_display_does_not_raise(self, capsys):
        """display() in ra stdout mà không raise exception."""
        cfg = HardwareConfig()
        cfg.display()
        captured = capsys.readouterr()
        assert "backend_url" in captured.out
        assert "charge_point_code" in captured.out


# ===========================================================================
# Unit Tests — OCPP message helpers
# ===========================================================================

class TestMakeCall:
    """Kiểm tra định dạng OCPP CALL message."""

    def test_call_format(self):
        """[2, msg_id, action, payload] — đúng định dạng OCPP 1.6J."""
        msg = _make_call("BootNotification", {"key": "value"})
        assert isinstance(msg, list)
        assert len(msg) == 4
        assert msg[0] == 2          # CALL type
        assert isinstance(msg[1], int)
        assert msg[2] == "BootNotification"
        assert msg[3] == {"key": "value"}

    def test_call_default_empty_payload(self):
        """Payload mặc định là dict rỗng."""
        msg = _make_call("Heartbeat")
        assert msg[3] == {}

    def test_call_msg_id_is_positive(self):
        """msg_id phải là số nguyên dương."""
        msg = _make_call("Heartbeat")
        assert msg[1] > 0

    def test_call_msg_id_unique(self):
        """Mỗi lần gọi tạo msg_id khác nhau (xác suất cao)."""
        ids = {_make_call("Heartbeat")[1] for _ in range(100)}
        assert len(ids) > 90  # ít nhất 90% là unique


class TestNowIso:
    """Kiểm tra timestamp ISO-8601 UTC."""

    def test_ends_with_z(self):
        """Timestamp kết thúc bằng Z (UTC)."""
        ts = _now_iso()
        assert ts.endswith("Z")

    def test_parseable_iso8601(self):
        """Timestamp phải parse được bằng datetime.fromisoformat."""
        from datetime import datetime
        ts = _now_iso()
        # Thay Z -> +00:00 để fromisoformat chấp nhận
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert dt.tzinfo is not None


# ===========================================================================
# Unit Tests — print_info
# ===========================================================================

class TestPrintInfo:
    """Kiểm tra hàm in thông tin module."""

    def test_print_info_outputs_project_name(self, capsys):
        """print_info() in ra tên dự án và thông tin nhóm."""
        print_info()
        captured = capsys.readouterr()
        assert "CSMS" in captured.out
        assert "TTCS_K8S4_N5" in captured.out
        assert "Sprint" in captured.out


# ===========================================================================
# Integration Tests (mock WebSocket / HTTP) — OcppSimulator
# ===========================================================================

class TestOcppSimulator:
    """Kiểm tra OcppSimulator với mock WebSocket."""

    def test_init_default_values(self):
        """Khởi tạo đúng URI và thuộc tính."""
        sim = OcppSimulator(code="CP-001", host="localhost", port=8000)
        assert sim.code == "CP-001"
        assert sim.uri == "ws://localhost:8000/ocpp/CP-001"
        assert sim._connected is False

    def test_init_custom_heartbeat(self):
        """Heartbeat interval có thể tùy chỉnh."""
        sim = OcppSimulator(heartbeat_interval=30)
        assert sim.heartbeat_interval == 30

    @pytest.mark.asyncio
    async def test_run_fails_gracefully_without_server(self):
        """run() không crash khi server không có — kết thúc bình thường."""
        sim = OcppSimulator(code="CP-NO-SERVER", host="127.0.0.2", port=9999)
        # Không raise exception, chỉ log lỗi và return
        await asyncio.wait_for(sim.run(), timeout=3.0)
        assert sim._connected is False

    @pytest.mark.asyncio
    async def test_send_skipped_when_not_connected(self):
        """Các hàm send_* không gửi khi chưa kết nối."""
        sim = OcppSimulator()
        # Không raise — chỉ return early
        await sim.send_meter_values(wh=500)
        await sim.send_start_transaction(id_tag="TEST")
        await sim.send_stop_transaction(transaction_id=1)


# ===========================================================================
# Integration Tests (mock HTTP / WS) — HardwareHealthChecker
# ===========================================================================

class TestHardwareHealthChecker:
    """Kiểm tra HardwareHealthChecker với mock."""

    def test_init(self):
        """Khởi tạo đúng URL."""
        checker = HardwareHealthChecker(
            backend_url="http://192.168.1.100:8000",
            charge_point_code="CP-001",
        )
        assert checker.backend_url == "http://192.168.1.100:8000"
        assert checker.charge_point_code == "CP-001"
        assert checker.results == {}

    @pytest.mark.asyncio
    async def test_run_returns_false_when_backend_unreachable(self):
        """Trả False khi backend không thể kết nối."""
        checker = HardwareHealthChecker(
            backend_url="http://127.0.0.2:9999",
            charge_point_code="CP-UNREACHABLE",
        )
        result = await checker.run()
        assert result is False

    @pytest.mark.asyncio
    async def test_http_check_ok_with_mock(self):
        """Kiểm tra HTTP health với mock httpx trả 200."""
        checker = HardwareHealthChecker()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"status": "ok"}'

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await checker._check_http_health()

        assert checker.results["http_health"]["ok"] is True
        assert checker.results["http_health"]["status"] == 200

    @pytest.mark.asyncio
    async def test_http_check_fail_on_500(self):
        """Kiểm tra HTTP: status 500 → ok=False."""
        checker = HardwareHealthChecker()

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await checker._check_http_health()

        assert checker.results["http_health"]["ok"] is False

    def test_report_all_pass(self, capsys):
        """_report() trả True khi tất cả ok=True."""
        checker = HardwareHealthChecker()
        checker.results = {
            "http_health":  {"ok": True},
            "ws_handshake": {"ok": True},
        }
        result = checker._report()
        assert result is True
        assert "PASS" in capsys.readouterr().out

    def test_report_one_fail(self, capsys):
        """_report() trả False khi có 1 mục ok=False."""
        checker = HardwareHealthChecker()
        checker.results = {
            "http_health":  {"ok": True},
            "ws_handshake": {"ok": False, "error": "connection refused"},
        }
        result = checker._report()
        assert result is False
        out = capsys.readouterr().out
        assert "FAIL" in out

    def test_report_skip_none(self, capsys):
        """_report() bỏ qua mục ok=None (dependency chưa cài)."""
        checker = HardwareHealthChecker()
        checker.results = {
            "http_health":  {"ok": None, "note": "httpx not installed"},
        }
        result = checker._report()
        assert result is True  # None không tính là fail


# ===========================================================================
# Entry point chạy test trực tiếp
# ===========================================================================

if __name__ == "__main__":
    import subprocess
    subprocess.run(
        ["python", "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=str(__import__("pathlib").Path(__file__).parent.parent),
    )
