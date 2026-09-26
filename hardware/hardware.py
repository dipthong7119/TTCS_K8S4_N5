"""
hardware/hardware.py — Module phần cứng trạm sạc (CSMS)
Tham chieu: SPRINT_1.md K-01, 03_SSD_SPEC.md

Gồm 3 phần:
  1. OCPP Simulator   — Giả lập trụ sạc kết nối WebSocket đến backend
  2. Health Check     — Kiểm tra kết nối phần cứng và trạng thái trạm
  3. Hardware Module  — Khởi tạo cơ bản, thông tin module, entry point

Yêu cầu: pip install websockets httpx
Chạy:    python hardware/hardware.py [--mode simulator|health|info]
"""

import asyncio
import json
import uuid
import time
import argparse
import logging
from datetime import datetime, timezone
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("csms.hardware")

# ---------------------------------------------------------------------------
# Thông tin module (Placeholder)
# ---------------------------------------------------------------------------

__version__ = "1.0.0"
__project__ = "CSMS — Nền tảng vận hành trạm sạc xe điện"
__team__    = "TTCS_K8S4_N5"
__sprint__  = "Sprint 1"


def print_info() -> None:
    """In thông tin module ra stdout."""
    print("=" * 60)
    print(f"  {__project__}")
    print(f"  Nhóm    : {__team__}")
    print(f"  Sprint  : {__sprint__}")
    print(f"  Phiên bản: v{__version__}")
    print(f"  Thời gian: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    print("Các chế độ chạy:")
    print("  python hardware.py --mode simulator  # Giả lập trụ sạc")
    print("  python hardware.py --mode health     # Kiểm tra kết nối")
    print("  python hardware.py --mode info       # Thông tin module")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Phần 1: OCPP Simulator — Giả lập trụ sạc WebSocket (K-01)
# ---------------------------------------------------------------------------

VENDOR   = "CSMS-Vendor"
MODEL    = "SimCharger-v1"
FIRMWARE = __version__


def _make_call(action: str, data: Optional[dict] = None) -> list:
    """Tạo khung CALL OCPP 1.6J: [2, message_id, action, payload]"""
    msg_id  = uuid.uuid4().int & 0x7FFFFF
    payload = data or {}
    return [2, msg_id, action, payload]


class OcppSimulator:
    """
    Giả lập trụ sạc OCPP 1.6J — kết nối WebSocket đến /ocpp/{code}.
    Gửi: BootNotification → Heartbeat định kỳ → StatusNotification.
    Hỗ trợ: StartTransaction, StopTransaction, MeterValues.
    """

    def __init__(
        self,
        code: str = "CP-TEST-01",
        host: str = "localhost",
        port: int = 8000,
        heartbeat_interval: int = 10,
    ):
        self.code               = code
        self.uri                = f"ws://{host}:{port}/ocpp/{code}"
        self.heartbeat_interval = heartbeat_interval
        self._ws                = None
        self._connected         = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Khởi động simulator: kết nối và giữ vòng lặp chính."""
        try:
            import websockets
        except ImportError:
            logger.error("Thiếu thư viện websockets. Chạy: pip install websockets")
            return

        logger.info("Đang kết nối đến %s", self.uri)
        try:
            async with websockets.connect(
                self.uri,
                subprotocols=["ocpp1.6"],
            ) as ws:
                self._ws        = ws
                self._connected = True
                logger.info("Đã kết nối — trụ sạc %s", self.code)
                await self._main_loop()
        except Exception as exc:
            logger.error("Kết nối thất bại: %s", exc)
        finally:
            self._connected = False
            logger.info("Đã ngắt kết nối — trụ sạc %s", self.code)

    async def send_start_transaction(self, id_tag: str = "USER-001") -> None:
        """Gửi StartTransaction."""
        if not self._connected:
            return
        msg = _make_call("StartTransaction", {
            "idTag":        id_tag,
            "connectorId":  1,
            "meterStart":   0,
            "timestamp":    _now_iso(),
        })
        await self._send(msg)

    async def send_stop_transaction(
        self,
        transaction_id: int,
        meter_stop: int = 5000,
    ) -> None:
        """Gửi StopTransaction."""
        if not self._connected:
            return
        msg = _make_call("StopTransaction", {
            "transactionId": transaction_id,
            "meterStop":     meter_stop,
            "timestamp":     _now_iso(),
        })
        await self._send(msg)

    async def send_meter_values(self, wh: int = 1500) -> None:
        """Gửi MeterValues (kWh giả lập)."""
        if not self._connected:
            return
        msg = _make_call("MeterValues", {
            "connectorId": 1,
            "meterValue": [{
                "timestamp": _now_iso(),
                "sampledValue": [{"value": str(wh), "unit": "Wh", "measurand": "Energy.Active.Import.Register"}],
            }],
        })
        await self._send(msg)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _main_loop(self) -> None:
        """Vòng lặp chính: BootNotification → StatusNotification → Heartbeat."""
        # 1. BootNotification
        boot = _make_call("BootNotification", {
            "chargePointVendor":          VENDOR,
            "chargePointModel":           MODEL,
            "chargePointFirmwareVersion": FIRMWARE,
        })
        await self._send(boot)

        # 2. StatusNotification — trạng thái Available
        status_msg = _make_call("StatusNotification", {
            "connectorId": 0,
            "errorCode":   "NoError",
            "status":      "Available",
            "timestamp":   _now_iso(),
        })
        await self._send(status_msg)

        # 3. Heartbeat định kỳ + lắng nghe message từ server
        recv_task = asyncio.create_task(self._recv_loop())
        try:
            while self._connected:
                await asyncio.sleep(self.heartbeat_interval)
                hb = _make_call("Heartbeat")
                await self._send(hb)
        finally:
            recv_task.cancel()

    async def _recv_loop(self) -> None:
        """Nhận và log message từ server."""
        try:
            async for raw in self._ws:
                try:
                    data = json.loads(raw)
                    logger.info("← Server: %s", data)
                except json.JSONDecodeError:
                    logger.warning("Nhận được dữ liệu không hợp lệ: %r", raw)
        except Exception as exc:
            logger.debug("Recv loop kết thúc: %s", exc)

    async def _send(self, msg: list) -> None:
        """Gửi message JSON và log."""
        try:
            raw = json.dumps(msg)
            await self._ws.send(raw)
            logger.info("→ Gửi %s (msg_id=%s)", msg[2] if len(msg) > 2 else "?", msg[1])
        except Exception as exc:
            logger.error("Lỗi gửi message: %s", exc)
            self._connected = False


# ---------------------------------------------------------------------------
# Phần 2: Hardware Health Check — Kiểm tra kết nối phần cứng và backend
# ---------------------------------------------------------------------------

class HardwareHealthChecker:
    """
    Kiểm tra kết nối giữa phần cứng (trụ sạc) và backend CSMS.
    Gồm 3 bước:
      1. Ping HTTP endpoint /health của backend
      2. Thử WebSocket handshake đến /ocpp/{code}
      3. Báo cáo tổng hợp trạng thái
    """

    def __init__(
        self,
        backend_url: str = "http://localhost:8000",
        charge_point_code: str = "CP-TEST-01",
    ):
        self.backend_url        = backend_url.rstrip("/")
        self.charge_point_code  = charge_point_code
        self.results: dict      = {}

    async def run(self) -> bool:
        """Chạy toàn bộ health check. Trả True nếu tất cả pass."""
        logger.info("=== Hardware Health Check ===")
        await self._check_http_health()
        await self._check_ws_handshake()
        return self._report()

    # ------------------------------------------------------------------

    async def _check_http_health(self) -> None:
        """Kiểm tra HTTP GET /health."""
        label = "http_health"
        url   = f"{self.backend_url}/health"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
            ok = resp.status_code == 200
            self.results[label] = {
                "ok":     ok,
                "status": resp.status_code,
                "body":   resp.text[:120],
            }
            _log_check(label, ok, f"HTTP {resp.status_code}")
        except ImportError:
            logger.warning("httpx chưa được cài. Bỏ qua kiểm tra HTTP.")
            self.results[label] = {"ok": None, "note": "httpx not installed"}
        except Exception as exc:
            self.results[label] = {"ok": False, "error": str(exc)}
            _log_check(label, False, str(exc))

    async def _check_ws_handshake(self) -> None:
        """Kiểm tra WebSocket handshake đến /ocpp/{code}."""
        label = "ws_handshake"
        ws_url = (
            self.backend_url
            .replace("http://", "ws://")
            .replace("https://", "wss://")
            + f"/ocpp/{self.charge_point_code}"
        )
        try:
            import websockets
            async with websockets.connect(
                ws_url,
                subprotocols=["ocpp1.6"],
                open_timeout=5,
                close_timeout=3,
            ) as ws:
                # Gửi BootNotification nhỏ để kiểm tra handshake
                boot = _make_call("BootNotification", {
                    "chargePointVendor": VENDOR,
                    "chargePointModel":  MODEL,
                })
                await ws.send(json.dumps(boot))
                raw = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(raw)
            self.results[label] = {"ok": True, "response": data}
            _log_check(label, True, "Handshake thành công")
        except ImportError:
            logger.warning("websockets chưa được cài. Bỏ qua kiểm tra WS.")
            self.results[label] = {"ok": None, "note": "websockets not installed"}
        except Exception as exc:
            self.results[label] = {"ok": False, "error": str(exc)}
            _log_check(label, False, str(exc))

    def _report(self) -> bool:
        """In báo cáo tổng hợp và trả về True nếu tất cả pass."""
        print("\n" + "=" * 50)
        print("KẾT QUẢ HEALTH CHECK")
        print("=" * 50)
        all_ok = True
        for name, result in self.results.items():
            ok = result.get("ok")
            if ok is None:
                symbol, label = "⚠ ", "BỎ QUA"
            elif ok:
                symbol, label = "✅", "PASS"
            else:
                symbol, label = "❌", "FAIL"
                all_ok = False
            print(f"  {symbol} {name:<20} {label}")
        print("=" * 50)
        print(f"Tổng kết: {'✅ Tất cả PASS' if all_ok else '❌ Có lỗi — xem chi tiết ở trên'}")
        print("=" * 50 + "\n")
        return all_ok


# ---------------------------------------------------------------------------
# Helpers dùng chung
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log_check(name: str, ok: bool, detail: str) -> None:
    if ok:
        logger.info("✅ [%s] PASS — %s", name, detail)
    else:
        logger.error("❌ [%s] FAIL — %s", name, detail)


# ---------------------------------------------------------------------------
# Entry point CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="CSMS Hardware Module — Simulator / Health Check / Info",
    )
    p.add_argument(
        "--mode",
        choices=["simulator", "health", "info"],
        default="info",
        help="Chế độ chạy (mặc định: info)",
    )
    p.add_argument("--host",  default="localhost",   help="Host backend (mặc định: localhost)")
    p.add_argument("--port",  default=8000, type=int, help="Port backend (mặc định: 8000)")
    p.add_argument("--code",  default="CP-TEST-01",  help="Mã trụ sạc (mặc định: CP-TEST-01)")
    return p


async def _async_main(args) -> None:
    if args.mode == "simulator":
        sim = OcppSimulator(code=args.code, host=args.host, port=args.port)
        await sim.run()
    elif args.mode == "health":
        checker = HardwareHealthChecker(
            backend_url=f"http://{args.host}:{args.port}",
            charge_point_code=args.code,
        )
        await checker.run()
    else:
        print_info()


def main() -> None:
    print_info()
    parser = _build_parser()
    args   = parser.parse_args()
    asyncio.run(_async_main(args))


if __name__ == "__main__":
    main()
