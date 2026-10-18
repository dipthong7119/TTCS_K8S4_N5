"""Independent OCPP 1.6J client and configurable fleet (K-01 / T-55).

The fleet uses registered SIM- codes from the adjacent seed_codes.txt and can
opt into the five seeded demo-station devices with their declared connectors.
Compose supplies configuration as CLI arguments; no server logic is imported.
"""

import argparse
import asyncio
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
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


class BootNotificationRejected(RuntimeError):
    """A server declined this device and specified when it may retry."""

    def __init__(self, code: str, result: dict[str, Any]) -> None:
        try:
            self.retry_after = max(1, int(result.get("interval", 10)))
        except (TypeError, ValueError):
            self.retry_after = 10
        super().__init__(f"{code}: BootNotification rejected: {result}")


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
        *, server_url: str | None = None, state_dir: str | Path | None = None,
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
        self.configuration = {
            "HeartbeatInterval": 10,
            "MeterValueSampleInterval": 30,
        }
        self._active_transactions: dict[int, dict[str, Any]] = {}
        configured_state_dir = state_dir if state_dir is not None else os.getenv(
            "CSMS_SIMULATOR_STATE_DIR"
        )
        safe_code = re.sub(r"[^A-Za-z0-9_.-]", "_", code)
        state_file_name = f"{safe_code}.json"
        self._state_path = (
            Path(configured_state_dir) / state_file_name
            if configured_state_dir
            else None
        )
        self._load_active_transactions()
        self._reservations: dict[int, int] = {}
        self._pending_calls: dict[str, asyncio.Future] = {}
        self._receiver_task: asyncio.Task | None = None
        self._reboot_requested = False
        self._disconnect_event = asyncio.Event()

    def _load_active_transactions(self) -> None:
        if self._state_path is None or not self._state_path.exists():
            return
        try:
            state = json.loads(self._state_path.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                raise TypeError("simulator state must be an object")
            transactions = state.get("active_transactions", {})
            if not isinstance(transactions, dict):
                raise TypeError("active_transactions must be an object")
            for raw_connector_id, transaction in transactions.items():
                try:
                    connector_id = int(raw_connector_id)
                except (TypeError, ValueError):
                    continue
                if not isinstance(transaction, dict):
                    continue
                transaction_id = transaction.get("transaction_id")
                meter_wh = transaction.get("meter_wh")
                stop_requested = transaction.get("stop_requested", False)
                stop_requested_at = transaction.get("stop_requested_at")
                if (
                    connector_id <= 0
                    or type(transaction_id) is not int
                    or transaction_id <= 0
                    or type(meter_wh) is not int
                    or meter_wh < 0
                    or type(stop_requested) is not bool
                    or (
                        stop_requested_at is not None
                        and not isinstance(stop_requested_at, str)
                    )
                ):
                    continue
                if stop_requested_at is not None:
                    try:
                        datetime.fromisoformat(stop_requested_at.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                self._active_transactions[connector_id] = {
                    "transaction_id": transaction_id,
                    "meter_wh": meter_wh,
                    "last_sample": time.monotonic(),
                    "stop_requested": stop_requested,
                    "stop_requested_at": stop_requested_at,
                }
        except (OSError, TypeError, ValueError) as exc:
            print(
                f"[Simulator {self.code}] Could not restore transaction state: {exc}",
                flush=True,
            )
            return
        if self._active_transactions:
            print(
                f"[Simulator {self.code}] Restored {len(self._active_transactions)} active transaction(s)",
                flush=True,
            )

    def _persist_active_transactions(self) -> None:
        if self._state_path is None:
            return
        state = {
            "version": 1,
            "active_transactions": {
                str(connector_id): {
                    "transaction_id": session["transaction_id"],
                    "meter_wh": session["meter_wh"],
                    "stop_requested": session.get("stop_requested", False),
                    "stop_requested_at": session.get("stop_requested_at"),
                }
                for connector_id, session in self._active_transactions.items()
            },
        }
        temp_path = self._state_path.with_suffix(".json.tmp")
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(json.dumps(state), encoding="utf-8")
            temp_path.replace(self._state_path)
        except OSError as exc:
            print(
                f"[Simulator {self.code}] Could not save transaction state: {exc}",
                flush=True,
            )

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
                        try:
                            transaction_id = int(payload.get("transactionId"))
                        except (TypeError, ValueError):
                            transaction_id = None
                        session = next(
                            (
                                transaction
                                for transaction in self._active_transactions.values()
                                if transaction["transaction_id"] == transaction_id
                            ),
                            None,
                        )
                        if session is None:
                            status = "Rejected"
                        else:
                            session["stop_requested"] = True
                            session["stop_requested_at"] = (
                                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                            )
                            self._persist_active_transactions()
                            status = "Accepted"
                        await self.ws.send(
                            json.dumps(make_callresult(message_id, {"status": status}))
                        )
                        if session is not None and transaction_id is not None:
                            asyncio.create_task(self._trigger_remote_stop(transaction_id))
                    elif action == "ReserveNow":
                        try:
                            reservation_id = int(payload["reservationId"])
                            connector_id = int(payload.get("connectorId", 0))
                        except (KeyError, TypeError, ValueError):
                            reservation_status = "Rejected"
                        else:
                            connector_is_reserved = connector_id in self._reservations.values()
                            if (
                                reservation_id <= 0
                                or connector_id < 1
                                or connector_id > self.profile.connector_count
                                or connector_is_reserved
                            ):
                                reservation_status = "Occupied" if connector_is_reserved else "Rejected"
                            else:
                                self._reservations[reservation_id] = connector_id
                                reservation_status = "Accepted"
                        await self.ws.send(
                            json.dumps(make_callresult(message_id, {"status": reservation_status}))
                        )
                    elif action == "CancelReservation":
                        try:
                            reservation_id = int(payload["reservationId"])
                        except (KeyError, TypeError, ValueError):
                            connector_id = None
                        else:
                            connector_id = self._reservations.pop(reservation_id, None)
                        reservation_status = "Accepted" if connector_id is not None else "Rejected"
                        await self.ws.send(
                            json.dumps(make_callresult(message_id, {"status": reservation_status}))
                        )
                        if connector_id is not None:
                            asyncio.create_task(self._notify_connector_available(connector_id))
                    elif action == "ChangeConfiguration":
                        key = payload.get("key")
                        limits = {
                            "HeartbeatInterval": (30, 3600),
                            "MeterValueSampleInterval": (5, 900),
                        }
                        status = "NotSupported"
                        if key in limits:
                            status = "Rejected"
                            try:
                                raw = payload.get("value")
                                value = int(raw) if isinstance(raw, str) else None
                                minimum, maximum = limits[key]
                                if value is not None and minimum <= value <= maximum:
                                    self.configuration[key] = value
                                    status = "Accepted"
                            except (ValueError, TypeError):
                                pass
                        await self.ws.send(
                            json.dumps(make_callresult(message_id, {"status": status}))
                        )
                    elif action == "GetConfiguration":
                        keys = payload.get("key") or list(self.configuration)
                        result = {
                            "configurationKey": [
                                {
                                    "key": key,
                                    "readonly": False,
                                    "value": str(self.configuration[key]),
                                }
                                for key in keys
                                if key in self.configuration
                            ],
                            "unknownKey": [
                                key for key in keys
                                if key not in self.configuration
                            ],
                        }
                        await self.ws.send(
                            json.dumps(make_callresult(message_id, result))
                        )

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
                for reservation_id, reserved_connector in tuple(self._reservations.items()):
                    if reserved_connector == connector_id:
                        self._reservations.pop(reservation_id, None)
                transaction_id = res.get("transactionId")
                if transaction_id is not None:
                    self._active_transactions[connector_id] = {
                        "transaction_id": transaction_id,
                        "meter_wh": 1000,
                        "last_sample": time.monotonic(),
                        "stop_requested": False,
                    }
                    self._persist_active_transactions()
                charging_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                await self._call("StatusNotification", {
                    "connectorId": connector_id,
                    "errorCode": "NoError",
                    "status": "Charging",
                    "timestamp": charging_iso,
                })
        except Exception:  # noqa: S110
            pass

    async def _notify_connector_available(self, connector_id: int) -> None:
        """Report the released connector after an accepted cancellation."""
        try:
            await self._call("StatusNotification", {
                "connectorId": connector_id,
                "errorCode": "NoError",
                "status": "Available",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            })
        except Exception:  # noqa: S110
            pass

    async def _trigger_remote_stop(self, transaction_id: int) -> None:
        """Dừng phiên sạc sau khi nhận RemoteStopTransaction."""
        match = next(
            (
                (connector_id, session)
                for connector_id, session in self._active_transactions.items()
                if session["transaction_id"] == transaction_id
            ),
            None,
        )
        if match is None:
            print(
                f"[Simulator {self.code}] Cannot stop unknown transaction {transaction_id}",
                flush=True,
            )
            return

        connector_id, session = match
        self._active_transactions.pop(connector_id, None)
        now_iso = session.get("stop_requested_at") or (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        try:
            await self._call("StopTransaction", {
                "transactionId": transaction_id,
                "meterStop": session["meter_wh"],
                "timestamp": now_iso,
                "reason": "Remote",
            })
        except Exception as exc:
            self._active_transactions[connector_id] = session
            print(
                f"[Simulator {self.code}] Remote stop failed for transaction {transaction_id}: {exc}",
                flush=True,
            )
            return
        self._persist_active_transactions()
        try:
            await self._call("StatusNotification", {
                "connectorId": connector_id,
                "errorCode": "NoError",
                "status": "Available",
                "timestamp": now_iso,
            })
        except Exception as exc:
            print(
                f"[Simulator {self.code}] Could not report available connector {connector_id}: {exc}",
                flush=True,
            )


    async def _run_loop(self):
        """Vòng lặp chính: gửi BootNotification, rồi Heartbeat định kỳ."""
        boot_result = await self._call("BootNotification", {
            "chargePointVendor": self.profile.vendor,
            "chargePointModel": self.profile.model,
            "firmwareVersion": FIRMWARE,
        })
        if boot_result.get("status") != "Accepted":
            raise BootNotificationRejected(self.code, boot_result)
        heartbeat_interval = max(1, int(boot_result.get("interval", 10)))
        self.configuration["HeartbeatInterval"] = heartbeat_interval
        # 0 describes the whole device; positive IDs describe every seeded connector.
        for connector_id in range(self.profile.connector_count + 1):
            await self._call("StatusNotification", {
                "connectorId": connector_id,
                "errorCode": self.profile.error_code,
                "status": self.profile.status,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            })
        print(f"[Simulator {self.code}] Boot accepted, interval={heartbeat_interval}s")

        # Resume an accepted remote stop after a simulator restart.
        pending_stops = [
            session["transaction_id"]
            for session in self._active_transactions.values()
            if session.get("stop_requested")
        ]
        for transaction_id in pending_stops:
            await self._trigger_remote_stop(transaction_id)

        last_heartbeat_tick = time.monotonic()
        while self.connected:
            try:
                await asyncio.wait_for(
                    self._disconnect_event.wait(),
                    timeout=1,
                )
                return
            except asyncio.TimeoutError:
                pass

            if not self.connected:
                return

            now = time.monotonic()
            if now - last_heartbeat_tick >= self.configuration["HeartbeatInterval"]:
                await self._call("Heartbeat")
                self.last_heartbeat = time.time()
                last_heartbeat_tick = time.monotonic()

            await self.send_meter_values()

    async def send_meter_values(self, timestamp: str | None = None):
        """Gửi MeterValues cho các phiên đang sạc đến kỳ lấy mẫu."""
        if not self.connected:
            return

        interval = self.configuration["MeterValueSampleInterval"]
        for connector_id, session in list(self._active_transactions.items()):
            if not self.connected:
                return
            if self._active_transactions.get(connector_id) is not session:
                continue

            now = time.monotonic()
            if now - session["last_sample"] < interval:
                continue

            session["meter_wh"] += 100
            session["last_sample"] = now
            self._persist_active_transactions()
            now_utc = timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            payload = {
                "connectorId": connector_id,
                "transactionId": session["transaction_id"],
                "meterValue": [{
                    "timestamp": now_utc,
                    "sampledValue": [{
                        "value": str(session["meter_wh"]),
                        "measurand": "Energy.Active.Import.Register",
                        "unit": "Wh",
                    }],
                }],
            }
            await self._call("MeterValues", payload)
            print(f"[Simulator {self.code}] Sent MeterValues at {now_utc}")

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
        if result.get("idTagInfo", {}).get("status") == "Accepted":
            transaction_id = result.get("transactionId")
            if transaction_id is not None:
                self._active_transactions[1] = {
                    "transaction_id": transaction_id,
                    "meter_wh": 0,
                    "last_sample": time.monotonic(),
                    "stop_requested": False,
                }
                self._persist_active_transactions()
        return result

    async def stop_transaction(self, transaction_id: int, meter_stop: int = 5000) -> dict | None:
        """Gửi StopTransaction."""
        if not self.connected:
            return None
        for connector_id, session in list(self._active_transactions.items()):
            if session["transaction_id"] == transaction_id:
                meter_stop = max(meter_stop, session["meter_wh"])
                self._active_transactions.pop(connector_id)
                removed = (connector_id, session)
                break
        else:
            removed = None
        try:
            result = await self._call("StopTransaction", {
                "transactionId": transaction_id,
                "meterStop": meter_stop,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "reason": "EVDisconnected",
            })
        except Exception:
            if removed is not None:
                self._active_transactions[removed[0]] = removed[1]
            raise
        self._persist_active_transactions()
        print("[Simulator] Sent StopTransaction")
        return result


async def run_simulator(
    code: str = "TEST-01", host: str = "localhost", port: int = 8000,
    *, server_url: str | None = None,
):
    """Chạy spike một lần kết nối đến server."""
    sim = SimpleSimulator(host=host, port=port, code=code, server_url=server_url)
    await sim.connect()


async def run_fleet(
    codes: tuple[str, ...], server_url: str, *, isolate_boot_rejections: bool = False,
) -> None:
    """Run sockets concurrently, optionally isolating BootNotification rejections."""
    simulators = [SimpleSimulator(code=code, server_url=server_url) for code in codes]
    if not simulators or len(set(codes)) != len(codes):
        raise ValueError("fleet requires at least one charge point and unique codes")

    async def connect(simulator: SimpleSimulator) -> None:
        while True:
            try:
                await simulator.connect()
                raise RuntimeError(f"{simulator.code}: connection ended unexpectedly")
            except BootNotificationRejected as exc:
                if not isolate_boot_rejections:
                    raise
                print(
                    f"[Simulator {simulator.code}] BootNotification rejected; "
                    f"retrying in {exc.retry_after}s",
                    flush=True,
                )
                await asyncio.sleep(exc.retry_after)

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
