"""Independent OCPP 1.6J client and configurable fleet (K-01 / T-55).

The fleet uses registered SIM- codes from the adjacent seed_codes.txt and can
opt into the five seeded demo-station devices with their declared connectors.
Compose supplies configuration as CLI arguments; no server logic is imported.
"""

import argparse
import asyncio
import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from websockets.typing import Subprotocol

# OCPP 1.6J message formats (mang trong module riêng — T-14)
# CALL:      [2, unique_id, action, payload]
# CALLRESULT: [3, unique_id, payload]
# CALLError:  [4, message_id, error_code, error_description, error_details]

VENDOR = "TestVendor"
MODEL = "TestModel"
FIRMWARE = "1.0.0"
SEED_CODES_FILE = Path(__file__).with_name("seed_codes.txt")


@dataclass(frozen=True)
class PointProfile:
    """Independent device settings matching the development seed inventory."""

    connector_count: int = 1
    vendor: str = VENDOR
    model: str = MODEL
    status: str = "Available"
    error_code: str = "NoError"


SIMULATOR_PROFILE = PointProfile(2, "CSMS Simulator", "OCPP 1.6J")
DEMO_POINT_PROFILES = {
    "CP_VINCOM_01": PointProfile(2, "VinFast", "VF-AC-11KW"),
    "CP_VINCOM_02": PointProfile(1, "ABB", "Terra 54"),
    "CP_AEON_01": PointProfile(3, "EVN", "EVN-FAST"),
    "CP_AEON_FAULT": PointProfile(1, "ABB", "Terra AC", "Faulted", "GroundFailure"),
    "CP_DEMO_MAINT_01": PointProfile(2, "Schneider", "EVlink", "Unavailable"),
}


def simulator_codes(
    count: int, codes_file: Path = SEED_CODES_FILE, *, include_demo_stations: bool = False,
) -> tuple[str, ...]:
    """Select registered SIM- codes and optional seeded demo-station devices."""
    codes = tuple(
        line.strip() for line in codes_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not codes or len(set(codes)) != len(codes) or any(
        not re.fullmatch(r"SIM-[0-9]+", code) for code in codes
    ):
        raise ValueError("seed_codes.txt must contain unique SIM- codes")
    if not 1 <= count <= len(codes):
        raise ValueError(f"count must be between 1 and {len(codes)} seeded charge points")
    selected = codes[:count]
    if include_demo_stations:
        selected += tuple(DEMO_POINT_PROFILES)
    return selected


def charge_point_uri(server_url: str, code: str) -> str:
    """Append the code to an OCPP base URL, including optional proxy path/TLS."""
    parsed = urlsplit(server_url)
    if (
        parsed.scheme not in {"ws", "wss"} or not parsed.hostname
        or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment
    ):
        raise ValueError("server URL must use ws:// or wss:// without credentials, query or fragment")
    # Accessing port also validates malformed/out-of-range ports.
    _ = parsed.port
    path = (parsed.path.rstrip("/") or "/ocpp") + "/" + quote(code, safe="")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


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

    def __init__(
        self, host: str = "localhost", port: int = 8000, code: str = "TEST-01",
        *, server_url: str | None = None,
    ):
        self.host = host
        self.port = port
        self.code = code
        self.profile = DEMO_POINT_PROFILES.get(
            code, SIMULATOR_PROFILE if code.startswith("SIM-") else PointProfile(),
        )
        self.uri = charge_point_uri(server_url or f"ws://{host}:{port}/ocpp", code)
        self.connected = False
        self.session_id = str(uuid.uuid4())
        self.last_heartbeat = time.time()
        self._pending_calls: dict[str, asyncio.Future] = {}
        self._receiver_task: asyncio.Task | None = None
        self._reboot_requested = False
        self._disconnect_event = asyncio.Event()

    async def connect(self):
        """Kết nối WebSocket đến server."""
        import websockets
        while True:
            self._disconnect_event.clear()
            self._reboot_requested = False
            async with websockets.connect(self.uri, subprotocols=[Subprotocol("ocpp1.6")]) as ws:
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
            if not self._reboot_requested:
                return
            await asyncio.sleep(1)

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
                    _, message_id, action, payload = data
                    if action == "Reset":
                        await self.ws.send(json.dumps(make_callresult(message_id, {"status": "Accepted"})))
                        self._reboot_requested = True
                        self._disconnect_event.set()
                        return
                    elif action == "RemoteStartTransaction":
                        await self.ws.send(json.dumps(make_callresult(message_id, {"status": "Accepted"})))
                        connector_id = int(payload.get("connectorId", 1))
                        id_tag = str(payload.get("idTag", "DEMO-DRIVER-0005"))
                        asyncio.create_task(self._trigger_remote_start(connector_id, id_tag))
                    elif action == "RemoteStopTransaction":
                        await self.ws.send(json.dumps(make_callresult(message_id, {"status": "Accepted"})))
                        transaction_id = int(payload.get("transactionId", 1))
                        asyncio.create_task(self._trigger_remote_stop(transaction_id))
        except websockets.ConnectionClosed:
            self.connected = False
            self._disconnect_event.set()
        except Exception as exc:
            self.connected = False
            self._disconnect_event.set()
            for future in self._pending_calls.values():
                if not future.done():
                    future.set_exception(exc)
            raise

    async def _trigger_remote_start(self, connector_id: int, id_tag: str) -> None:
        """Kích hoạt phiên sạc sau khi chấp nhận RemoteStartTransaction."""
        try:
            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            await self._call("StatusNotification", {
                "connectorId": connector_id,
                "errorCode": "NoError",
                "status": "Preparing",
                "timestamp": now_iso,
            })
            res = await self._call("StartTransaction", {
                "connectorId": connector_id,
                "idTag": id_tag,
                "meterStart": 1000,
                "timestamp": now_iso,
            })
            if isinstance(res, dict) and res.get("idTagInfo", {}).get("status") == "Accepted":
                charging_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                await self._call("StatusNotification", {
                    "connectorId": connector_id,
                    "errorCode": "NoError",
                    "status": "Charging",
                    "timestamp": charging_iso,
                })
        except Exception:  # noqa: S110
            pass

    async def _trigger_remote_stop(self, transaction_id: int) -> None:
        """Dừng phiên sạc sau khi nhận RemoteStopTransaction."""
        try:
            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            await self._call("StopTransaction", {
                "transactionId": transaction_id,
                "meterStop": 2500,
                "timestamp": now_iso,
                "reason": "Remote",
            })
            for cid in range(1, self.profile.connector_count + 1):
                await self._call("StatusNotification", {
                    "connectorId": cid,
                    "errorCode": "NoError",
                    "status": "Available",
                    "timestamp": now_iso,
                })
        except Exception:  # noqa: S110
            pass


    async def _run_loop(self):
        """Vòng lặp chính: gửi BootNotification, rồi Heartbeat định kỳ."""
        boot_result = await self._call("BootNotification", {
            "chargePointVendor": self.profile.vendor,
            "chargePointModel": self.profile.model,
            "firmwareVersion": FIRMWARE,
        })
        if boot_result.get("status") != "Accepted":
            raise RuntimeError(f"BootNotification rejected: {boot_result}")
        heartbeat_interval = max(1, int(boot_result.get("interval", 10)))
        # 0 describes the whole device; positive IDs describe every seeded connector.
        for connector_id in range(self.profile.connector_count + 1):
            await self._call("StatusNotification", {
                "connectorId": connector_id,
                "errorCode": self.profile.error_code,
                "status": self.profile.status,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            })
        print(f"[Simulator {self.code}] Boot accepted, interval={heartbeat_interval}s")

        while self.connected:
            try:
                await asyncio.wait_for(self._disconnect_event.wait(), timeout=heartbeat_interval)
                return
            except asyncio.TimeoutError:
                pass
            if not self.connected:
                return
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


async def run_simulator(
    code: str = "TEST-01", host: str = "localhost", port: int = 8000,
    *, server_url: str | None = None,
):
    """Chạy spike một lần kết nối đến server."""
    sim = SimpleSimulator(host=host, port=port, code=code, server_url=server_url)
    await sim.connect()


async def run_fleet(codes: tuple[str, ...], server_url: str) -> None:
    """Run independent sockets concurrently; stop the fleet if a device fails."""
    simulators = [SimpleSimulator(code=code, server_url=server_url) for code in codes]
    if not simulators or len(set(codes)) != len(codes):
        raise ValueError("fleet requires at least one charge point and unique codes")

    async def connect(simulator: SimpleSimulator) -> None:
        await simulator.connect()
        raise RuntimeError(f"{simulator.code}: connection ended unexpectedly")

    tasks = [asyncio.create_task(connect(simulator), name=simulator.code) for simulator in simulators]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run a virtual OCPP 1.6J charge point")
    parser.add_argument("code", nargs="?", help="Single registered code (legacy mode)")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--count", type=int, help="Number of seeded SIM- points to run concurrently")
    parser.add_argument("--server-url", help="OCPP base URL, e.g. ws://app:8000/ocpp")
    parser.add_argument(
        "--include-demo-stations", choices=("true", "false"), default="false",
        help="Also connect the five seeded Vincom/AEON/Thu Thiem demo points",
    )
    args = parser.parse_args(argv)
    if args.count is not None and args.code is not None:
        parser.error("use either a single code or --count")
    if args.include_demo_stations == "true" and args.count is None:
        parser.error("--include-demo-stations true requires --count")
    server_url = args.server_url or f"ws://{args.host}:{args.port}/ocpp"
    try:
        charge_point_uri(server_url, "SIM-01")
        codes = simulator_codes(
            args.count, include_demo_stations=args.include_demo_stations == "true",
        ) if args.count is not None else None
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if codes is None:
        asyncio.run(run_simulator(code=args.code or "TEST-01", server_url=server_url))
    else:
        print(f"[Simulator] Starting {len(codes)} charge points: {', '.join(codes)}", flush=True)
        asyncio.run(run_fleet(codes, server_url))


if __name__ == "__main__":
    main()
