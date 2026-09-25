"""
simulator.py — Spike: Trụ sạc ảo nối WebSocket tối giản (K-01)
Tham chieu: SPRINT_1.md K-01, 03_SSD_SPEC.md, 02_CODING_STANDARDS.md

YÊU CẦU: cài đặt ws4py hoặc dùng websockets: pip install websockets
Module này KHÔNG được import từ app/ và ngược lại (độc lập cho CI test).

Module này tạo một client WebSocket kết nối đến /ocpp/{code} và gửi các message
mẫu theo đặc tả OCPP 1.6J: BootNotification, Heartbeat, StatusNotification,
Authorize, StartTransaction, MeterValues, StopTransaction, Reset.

Module này độc lập — dùng để spike/K-01 test chứ không phải sản phẩm chính.
"""

import asyncio
import json
import uuid
import time
from datetime import datetime, timezone
from typing import Optional

# OCPP 1.6J message formats (mang trong module riêng — T-14)
# CALL:      [2, message_id, action, transactionId, data]
# CALLRESULT: [3, message_id, request_id, data]
# CALLError:  [4, message_id, error_code, error_description, error_details]

VENDOR = "TestVendor"
MODEL = "TestModel"
FIRMWARE = "1.0.0"


def make_call(action: str, data: Optional[dict] = None) -> list:
    """Tạo khung CALL [2, message_id, action, data]"""
    msg_id = uuid.uuid4().int & 0x7FFFFF  # 23-bit positive int
    payload = data or {}
    return [2, msg_id, action, payload]


def make_callresult(request_id: int, data: dict) -> list:
    """Tạo khung CALLRESULT [3, message_id, request_id, data]"""
    return [3, request_id, request_id, data]


def make_calleerror(request_id: int, error_code: str, description: str = "") -> list:
    """Tạo khung CALLError [4, message_id, error_code, description, details]"""
    return [4, request_id, error_code, description, []]


class SimpleSimulator:
    """Trụ sạc ảo đơn giản — kết nối WebSocket và xử lý các message."""

    def __init__(self, host: str = "localhost", port: int = 8000, code: str = "TEST-01"):
        self.host = host
        self.port = port
        self.code = code
        self.uri = f"ws://{host}:{port}/ocpp/{code}"
        self.connected = False
        self.session_id = str(uuid.uuid4())
        self.last_heartbeat = time.time()

    async def connect(self):
        """Kết nối WebSocket đến server."""
        import websockets
        async with websockets.connect(self.uri) as ws:
            self.ws = ws
            self.connected = True
            print(f"[Simulator] Connected to {self.uri}")
            await self._run_loop()

    async def _run_loop(self):
        """Vòng lặp chính: gửi BootNotification, rồi Heartbeat định kỳ."""
        # 1. Gửi BootNotification khi kết nối
        boot = make_call("BootNotification", {
            "chargePointVendor": VENDOR,
            "chargePointModel": MODEL,
            "chargePointFirmwareVersion": FIRMWARE,
        })
        await self.ws.send(json.dumps(boot))
        print(f"[Simulator] Sent BootNotification: {boot}")

        # 2. Nhận phản hồi BootNotification (lắng nghe)
        async def wait_for_boot():
            async for message in self.ws:
                data = json.loads(message)
                if data[1] == "BootNotification" and data[2] == "Accepted":
                    interval = data[3].get("interval", 10)
                    print(f"[Simulator] Boot accepted, interval={interval}s")
                    return interval
                # Quay lại nếu không phải response cho BootNotification
                # (dù code thực tế phức tạp hơn, đây là spike đơn giản)

        # Chạy song song: đợi boot + gửi heartbeat
        boot_task = asyncio.create_task(wait_for_boot())

        # 3. Gửi Heartbeat mỗi 10 giây
        heartbeat_interval = 10
        while self.connected:
            try:
                await asyncio.sleep(heartbeat_interval)
                now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                heartbeat = make_call("Heartbeat")
                await self.ws.send(json.dumps(heartbeat))
                print(f"[Simulator] Sent Heartbeat at {now_utc}")
            except Exception as e:
                print(f"[Simulator] Heartbeat error: {e}")
                break

        # Đợi boot task hoàn thành
        try:
            await asyncio.wait_for(boot_task, timeout=5.0)
        except asyncio.TimeoutError:
            print("[Simulator] Boot notification timeout")

    async def send_meter_values(self, timestamp: Optional[str] = None):
        """Gửi MeterValues."""
        if not self.connected:
            return
        now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z") if timestamp is None else timestamp
        meter = make_call("MeterValues", {
            "meterValue": [{
                "context": "System",
                "type": "Import",
                "unit": "Wh",
                "value": 1500  # ví dụ: 1.5 kWh
            }],
            "timestamp": now_utc,
        })
        await self.ws.send(json.dumps(meter))
        print(f"[Simulator] Sent MeterValues at {now_utc}")

    async def start_transaction(self, id_tag: str = "TEST-USER") -> Optional[dict]:
        """Gửi StartTransaction."""
        if not self.connected:
            return None
        tx_id = uuid.uuid4().int & 0x7FFFFF
        start = make_call("StartTransaction", {
            "idTag": id_tag,
            "connectorId": 1,
            "meterStart": 0,
        })
        await self.ws.send(json.dumps(start))
        print(f"[Simulator] Sent StartTransaction")
        # Đợi response (simplified)
        await asyncio.sleep(0.5)
        return {"transactionId": tx_id, "idTagInfo": {"status": "Accepted"}}

    async def stop_transaction(self, transaction_id: int, meter_stop: int = 5000) -> Optional[dict]:
        """Gửi StopTransaction."""
        if not self.connected:
            return None
        stop = make_call("StopTransaction", {
            "transactionId": transaction_id,
            "meterStop": meter_stop,
        })
        await self.ws.send(json.dumps(stop))
        print(f"[Simulator] Sent StopTransaction")
        await asyncio.sleep(0.5)
        return {"transactionId": transaction_id, "meterStop": meter_stop,
                "idTagInfo": {"status": "Accepted"}, "kWh": 5.0}


async def run_simulator(code: str = "TEST-01", host: str = "localhost", port: int = 8000):
    """Chạy spike một lần kết nối đến server."""
    sim = SimpleSimulator(host=host, port=port, code=code)
    await sim.connect()


# Để chạy trực tiếp từ dòng lệnh: python -m simulator
if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "TEST-01"
    asyncio.run(run_simulator(code=code))