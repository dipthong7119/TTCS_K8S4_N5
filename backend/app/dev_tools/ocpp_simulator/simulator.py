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
import time
import uuid
from datetime import datetime, timezone

# OCPP 1.6J message formats (mang trong module riêng — T-14)
# CALL:      [2, unique_id, action, payload]
# CALLRESULT: [3, unique_id, payload]
# CALLError:  [4, message_id, error_code, error_description, error_details]

VENDOR = "TestVendor"
MODEL = "TestModel"
FIRMWARE = "1.0.0"


def make_call(action: str, data: dict | None = None) -> list:
    """Tạo khung CALL [2, message_id, action, data]"""
    msg_id = uuid.uuid4().hex
    payload = data or {}
    return [2, msg_id, action, payload]


def make_callresult(request_id: str, data: dict) -> list:
    """Tạo khung CALLRESULT OCPP 1.6J: [3, unique_id, payload]."""
    return [3, str(request_id), data]


def make_calleerror(request_id: str, error_code: str, description: str = "") -> list:
    """Tạo khung CALLError [4, message_id, error_code, description, details]"""
    return [4, str(request_id), error_code, description, {}]


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
        self._pending_calls: dict[str, asyncio.Future] = {}
        self._receiver_task: asyncio.Task | None = None

    async def connect(self):
        """Kết nối WebSocket đến server."""
        import websockets
        async with websockets.connect(self.uri, subprotocols=["ocpp1.6"]) as ws:
            self.ws = ws
            self.connected = True
            print(f"[Simulator] Connected to {self.uri}")
            self._receiver_task = asyncio.create_task(self._receive_loop())
            try:
                await self._run_loop()
            finally:
                self.connected = False
                if not self._receiver_task.done():
                    self._receiver_task.cancel()
                    await asyncio.gather(self._receiver_task, return_exceptions=True)

    async def _call(self, action: str, payload: dict | None = None, timeout: float = 5.0) -> dict:
        """Send a CALL and return only its matching CALLRESULT payload."""
        call = make_call(action, payload)
        response_future = asyncio.get_running_loop().create_future()
        self._pending_calls[call[1]] = response_future
        try:
            await self.ws.send(json.dumps(call))
            return await asyncio.wait_for(response_future, timeout=timeout)
        finally:
            self._pending_calls.pop(call[1], None)

    async def _receive_loop(self) -> None:
        """Resolve correlated results and answer the minimal server Reset call."""
        import websockets

        try:
            async for message in self.ws:
                data = json.loads(message)
                if not isinstance(data, list) or len(data) < 3:
                    continue
                if data[0] == 3:
                    future = self._pending_calls.get(str(data[1]))
                    if future and not future.done():
                        future.set_result(data[2])
                elif data[0] == 4:
                    future = self._pending_calls.get(str(data[1]))
                    if future and not future.done():
                        future.set_exception(RuntimeError(f"OCPP {data[2]}: {data[3]}"))
                elif data[0] == 2:
                    _, message_id, action, _payload = data
                    if action == "Reset":
                        await self.ws.send(json.dumps(make_callresult(message_id, {"status": "Accepted"})))
        except websockets.ConnectionClosed:
            self.connected = False
        except Exception as exc:
            self.connected = False
            for future in self._pending_calls.values():
                if not future.done():
                    future.set_exception(exc)
            raise

    async def _run_loop(self):
        """Vòng lặp chính: gửi BootNotification, rồi Heartbeat định kỳ."""
        boot_result = await self._call("BootNotification", {
            "chargePointVendor": VENDOR,
            "chargePointModel": MODEL,
            "firmwareVersion": FIRMWARE,
        })
        if boot_result.get("status") != "Accepted":
            raise RuntimeError(f"BootNotification rejected: {boot_result}")
        heartbeat_interval = max(1, int(boot_result.get("interval", 10)))
        await self._call("StatusNotification", {
            "connectorId": 0,
            "errorCode": "NoError",
            "status": "Available",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
        print(f"[Simulator] Boot accepted, interval={heartbeat_interval}s")

        while self.connected:
            await asyncio.sleep(heartbeat_interval)
            await self._call("Heartbeat")
            self.last_heartbeat = time.time()

    async def send_meter_values(self, timestamp: str | None = None):
        """Gửi MeterValues."""
        if not self.connected:
            return
        now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z") if timestamp is None else timestamp
        payload = {
            "connectorId": 1,
            "transactionId": 1,
            "meterValue": [{
                "timestamp": now_utc,
                "sampledValue": [{
                    "value": "1.5",
                    "measurand": "Energy.Active.Import.Register",
                    "unit": "kWh",
                }],
            }],
        }
        await self._call("MeterValues", payload)
        print(f"[Simulator] Sent MeterValues at {now_utc}")

    async def start_transaction(self, id_tag: str = "TEST-USER") -> dict | None:
        """Gửi StartTransaction."""
        if not self.connected:
            return None
        result = await self._call("StartTransaction", {
            "idTag": id_tag,
            "connectorId": 1,
            "meterStart": 0,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
        print("[Simulator] Sent StartTransaction")
        return result

    async def stop_transaction(self, transaction_id: int, meter_stop: int = 5000) -> dict | None:
        """Gửi StopTransaction."""
        if not self.connected:
            return None
        result = await self._call("StopTransaction", {
            "transactionId": transaction_id,
            "meterStop": meter_stop,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "reason": "EVDisconnected",
        })
        print("[Simulator] Sent StopTransaction")
        return result


async def run_simulator(code: str = "TEST-01", host: str = "localhost", port: int = 8000):
    """Chạy spike một lần kết nối đến server."""
    sim = SimpleSimulator(host=host, port=port, code=code)
    await sim.connect()


# Để chạy trực tiếp từ dòng lệnh: python -m simulator
if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "TEST-01"
    asyncio.run(run_simulator(code=code))
