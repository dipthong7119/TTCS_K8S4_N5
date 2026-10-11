"""Kịch bản OCPP reconnect độc lập, dùng SQLite tạm nếu không chỉ định server."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, create_engine, text

from app.ocpp.session_statuses import OPEN_SESSION_STATUSES

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
logger = logging.getLogger("reconnect_scenario")
ENERGY_MEASURAND = "Energy.Active.Import.Register"


@dataclass(frozen=True)
class ScenarioConfig:
    chargers: int = 20
    max_disconnects: int = 3
    seed: int = 42
    tick_seconds: float = 0.2
    samples: int = 8
    repeats: int = 3
    boot_on_reconnect: bool = True
    server_url: str | None = None
    database_url: str | None = None
    codes: tuple[str, ...] = ()
    id_tag: str | None = None


@dataclass
class RunResult:
    code: str
    transaction_id: int | None
    meter_start_wh: int
    meter_stop_wh: int | None
    expected_kwh: Decimal | None
    ended_at: str | None
    disconnects: int
    sample_count: int
    error: str | None = None


@dataclass
class Comparison:
    code: str
    transaction_id: int | None
    meter_start_wh: int
    meter_stop_wh: int | None
    expected_kwh: Decimal | None
    actual_kwh: Decimal | None
    disconnects: int
    samples_sent: int
    samples_saved: int
    status: str
    ok: bool
    errors: list[str]


@dataclass(frozen=True)
class ChargerPlan:
    disconnect_count: int
    end_offline: bool
    available_before_stop: bool


def build_plans(seed: int, chargers: int, max_disconnects: int) -> list[ChargerPlan]:
    """Sinh kế hoạch ngắt lặp lại được và có đủ hai thứ tự đóng phiên."""
    rng = random.Random(seed)
    indices = list(range(chargers))
    rng.shuffle(indices)
    offline_count = chargers // 2
    offline_enders = set(indices[:offline_count])
    first_available_count = offline_count // 2
    first_available = set(indices[:first_available_count])
    plans: list[ChargerPlan] = []
    for index in range(chargers):
        plans.append(ChargerPlan(
            disconnect_count=rng.randint(1, max_disconnects),
            end_offline=index in offline_enders,
            available_before_stop=index in first_available,
        ))
    return plans


def evaluate_results(
    expected: list[RunResult],
    sessions_by_code: dict[str, list[dict[str, Any]]],
    samples_by_session: dict[int, int],
) -> list[Comparison]:
    """So kết quả cơ sở dữ liệu với đáp án Wh do từng trụ giữ."""
    comparisons: list[Comparison] = []
    for item in expected:
        faults: list[str] = []
        rows = sessions_by_code.get(item.code, [])
        actual: Decimal | None = None
        saved_samples = 0
        status = "missing"
        if item.error:
            faults.append(item.error)
        if len(rows) != 1:
            faults.append(f"số phiên={len(rows)}, cần đúng 1")
        if rows:
            row = rows[0]
            status = str(row.get("status") or "missing")
            if item.transaction_id != row.get("id"):
                faults.append(f"transactionId={row.get('id')}, mong đợi={item.transaction_id}")
            if status != "completed" or status in OPEN_SESSION_STATUSES:
                faults.append(f"trạng thái={status}, phiên chưa hoàn tất")
            if row.get("ended_at") is None:
                faults.append("thiếu ended_at")
            elif item.ended_at and _as_utc_string(row["ended_at"]) != item.ended_at:
                faults.append(
                    f"ended_at={_as_utc_string(row['ended_at'])}, mong đợi={item.ended_at}"
                )
            if row.get("meter_start_wh") != item.meter_start_wh:
                faults.append("meter_start_wh không khớp")
            if row.get("meter_stop_wh") != item.meter_stop_wh:
                faults.append("meter_stop_wh không khớp")
            raw_actual = row.get("energy_kwh")
            actual = Decimal(str(raw_actual)) if raw_actual is not None else None
            if actual != item.expected_kwh:
                faults.append(f"kWh={actual}, mong đợi={item.expected_kwh}")
            saved_samples = samples_by_session.get(int(row["id"]), 0)
        if saved_samples != item.sample_count:
            faults.append(f"số mẫu lưu={saved_samples}, đã gửi={item.sample_count}")
        comparisons.append(Comparison(
            code=item.code,
            transaction_id=item.transaction_id,
            meter_start_wh=item.meter_start_wh,
            meter_stop_wh=item.meter_stop_wh,
            expected_kwh=item.expected_kwh,
            actual_kwh=actual,
            disconnects=item.disconnects,
            samples_sent=item.sample_count,
            samples_saved=saved_samples,
            status=status,
            ok=not faults,
            errors=faults,
        ))
    return comparisons


def _as_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _as_utc_string(value: datetime | str) -> str:
    return _as_datetime(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def _utc_string(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class VirtualCharger:
    """Trụ OCPP 1.6J tối giản; không dùng simulator của ứng dụng."""

    def __init__(self, ws_base: str, code: str) -> None:
        self.code = code
        self.uri = f"{ws_base.rstrip('/')}/{code}"
        self.websocket: Any = None
        self.receiver: asyncio.Task[None] | None = None
        self.pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self.message_number = 0

    async def connect(self) -> None:
        import websockets

        self.websocket = await websockets.connect(
            self.uri,
            subprotocols=["ocpp1.6"],
            open_timeout=10,
            close_timeout=1,
            ping_interval=None,
        )
        self.receiver = asyncio.create_task(self._receive())

    async def disconnect_abruptly(self) -> None:
        """Đóng TCP mà không gửi khung Close WebSocket."""
        if self.websocket is None:
            return
        transport = getattr(self.websocket, "transport", None)
        if transport is None:
            transport = getattr(self.websocket, "_transport", None)
        if transport is not None:
            transport.abort()
        else:
            await self.websocket.close()
        await self._stop_receiver()
        self.websocket = None

    async def close(self) -> None:
        if self.websocket is not None:
            await self.websocket.close()
        await self._stop_receiver()
        self.websocket = None

    async def _stop_receiver(self) -> None:
        if self.receiver is not None and not self.receiver.done():
            self.receiver.cancel()
            await asyncio.gather(self.receiver, return_exceptions=True)
        self.receiver = None

    async def _receive(self) -> None:
        try:
            async for raw in self.websocket:
                frame = json.loads(raw)
                if not isinstance(frame, list) or len(frame) < 3:
                    continue
                kind = frame[0]
                message_id = str(frame[1])
                future = self.pending.get(message_id)
                if future is None or future.done():
                    continue
                if kind == 3:
                    future.set_result(frame[2])
                elif kind == 4:
                    future.set_exception(RuntimeError(f"OCPP CALLERROR: {frame[2]}"))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(exc)

    async def call(
        self, action: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if self.websocket is None:
            raise ConnectionError(f"{self.code}: WebSocket chưa kết nối")
        self.message_number += 1
        message_id = f"{self.code}-{self.message_number}"
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self.pending[message_id] = future
        try:
            await self.websocket.send(json.dumps([2, message_id, action, payload or {}]))
            return await asyncio.wait_for(future, timeout=10)
        finally:
            self.pending.pop(message_id, None)


def _sample(timestamp: datetime, value_wh: int) -> dict[str, Any]:
    return {
        "timestamp": _utc_string(timestamp),
        "sampledValue": [{
            "value": str(value_wh),
            "measurand": ENERGY_MEASURAND,
            "unit": "Wh",
        }],
    }


async def _run_charger(
    ws_base: str,
    code: str,
    id_tag: str,
    plan: ChargerPlan,
    rng: random.Random,
    *,
    samples: int,
    tick_seconds: float,
    boot_on_reconnect: bool,
) -> RunResult:
    meter_start = rng.randint(10_000, 40_000)
    meter_current = meter_start
    transaction_id: int | None = None
    sample_count = 0
    actual_disconnects = 0
    error: str | None = None
    # Đồng hồ trụ chạy trước thời điểm nhận để số đo bù thực sự nằm trong quá khứ.
    base_time = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=1)
    ended_at: str | None = None
    client = VirtualCharger(ws_base, code)

    async def send_sample(sample: dict[str, Any]) -> None:
        nonlocal sample_count
        await client.call("MeterValues", {
            "connectorId": 1,
            "transactionId": transaction_id,
            "meterValue": [sample],
        })
        sample_count += 1

    def increase_meter(timestamp: datetime) -> dict[str, Any]:
        nonlocal meter_current
        meter_current += rng.randint(100, 1500)
        return _sample(timestamp, meter_current)

    try:
        await client.connect()
        boot = await client.call("BootNotification", {
            "chargePointVendor": "CSMS-Reconnect-Test",
            "chargePointModel": "VirtualOCPP16",
        })
        if boot.get("status") != "Accepted":
            raise RuntimeError(f"BootNotification bị từ chối: {boot}")
        await client.call("StatusNotification", {
            "connectorId": 1, "status": "Available", "errorCode": "NoError",
        })
        authorized = await client.call("Authorize", {"idTag": id_tag})
        if authorized.get("idTagInfo", {}).get("status") != "Accepted":
            raise RuntimeError(f"Authorize bị từ chối: {authorized}")
        started = await client.call("StartTransaction", {
            "connectorId": 1,
            "idTag": id_tag,
            "meterStart": meter_start,
            "timestamp": _utc_string(base_time),
        })
        if started.get("idTagInfo", {}).get("status") != "Accepted":
            raise RuntimeError(f"StartTransaction bị từ chối: {started}")
        transaction_id = int(started["transactionId"])
        await client.call("StatusNotification", {
            "connectorId": 1, "status": "Charging", "errorCode": "NoError",
        })

        cuts = sorted(rng.sample(range(1, samples), plan.disconnect_count))
        outage_number = 0
        timestamp_step = 0

        for sample_index in range(samples):
            if sample_index in cuts:
                outage_number += 1
                await client.disconnect_abruptly()
                actual_disconnects += 1
                backlog: list[dict[str, Any]] = []
                for _ in range(rng.randint(1, 2)):
                    timestamp_step += 1
                    backlog.append(increase_meter(base_time + timedelta(seconds=timestamp_step)))
                should_stop_offline = plan.end_offline and outage_number == plan.disconnect_count
                queued_stop: dict[str, Any] | None = None
                if should_stop_offline:
                    timestamp_step += 1
                    ended_at = _utc_string(base_time + timedelta(seconds=timestamp_step))
                    queued_stop = {
                        "transactionId": transaction_id,
                        "meterStop": meter_current,
                        "timestamp": ended_at,
                        "reason": "EVDisconnected",
                        # Giữ nguyên transactionData trong hàng đợi ngoại tuyến.
                        "transactionData": backlog,
                    }
                await asyncio.sleep(max(tick_seconds, 0.05))
                await client.connect()
                if boot_on_reconnect:
                    resumed_boot = await client.call("BootNotification", {
                        "chargePointVendor": "CSMS-Reconnect-Test",
                        "chargePointModel": "VirtualOCPP16",
                    })
                    if resumed_boot.get("status") != "Accepted":
                        raise RuntimeError(f"BootNotification nối lại bị từ chối: {resumed_boot}")

                if should_stop_offline and plan.available_before_stop:
                    await client.call("StatusNotification", {
                        "connectorId": 1, "status": "Available", "errorCode": "NoError",
                    })
                elif not should_stop_offline:
                    await client.call("StatusNotification", {
                        "connectorId": 1, "status": "Charging", "errorCode": "NoError",
                    })

                for queued_sample in backlog:
                    await send_sample(queued_sample)

                if should_stop_offline:
                    stopped = await client.call("StopTransaction", queued_stop)
                    if stopped.get("idTagInfo", {}).get("status") != "Accepted":
                        raise RuntimeError(f"StopTransaction bù bị từ chối: {stopped}")
                    if not plan.available_before_stop:
                        await client.call("StatusNotification", {
                            "connectorId": 1,
                            "status": "Available",
                            "errorCode": "NoError",
                        })
                    break

            timestamp_step += 1
            sample = increase_meter(base_time + timedelta(seconds=timestamp_step))
            await send_sample(sample)
            await asyncio.sleep(tick_seconds)

        if ended_at is None:
            timestamp_step += 1
            ended_at = _utc_string(base_time + timedelta(seconds=timestamp_step))
            stopped = await client.call("StopTransaction", {
                "transactionId": transaction_id,
                "meterStop": meter_current,
                "timestamp": ended_at,
                "reason": "EVDisconnected",
            })
            if stopped.get("idTagInfo", {}).get("status") != "Accepted":
                raise RuntimeError(f"StopTransaction bị từ chối: {stopped}")
            await client.call("StatusNotification", {
                "connectorId": 1, "status": "Available", "errorCode": "NoError",
            })
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        await client.close()

    meter_stop = meter_current if transaction_id is not None else None
    expected_kwh = (
        Decimal(meter_current - meter_start) / Decimal(1000)
        if transaction_id is not None
        else None
    )
    return RunResult(
        code=code,
        transaction_id=transaction_id,
        meter_start_wh=meter_start,
        meter_stop_wh=meter_stop,
        expected_kwh=expected_kwh,
        ended_at=ended_at,
        disconnects=actual_disconnects,
        sample_count=sample_count,
        error=error,
    )


def _database_snapshot(
    database_url: str, codes: tuple[str, ...], after_session_id: int
) -> dict[str, Any]:
    engine = create_engine(database_url)
    try:
        code_bind = bindparam("codes", expanding=True)
        with engine.connect() as connection:
            session_rows = connection.execute(
                text(
                    "SELECT id, charge_point_code, status, meter_start_wh, meter_stop_wh, "
                    "energy_kwh, ended_at FROM charging_sessions "
                    "WHERE id > :after_id AND charge_point_code IN :codes"
                ).bindparams(code_bind),
                {"codes": list(codes), "after_id": after_session_id},
            ).mappings().all()
            ids = [int(row["id"]) for row in session_rows]
            sample_counts: dict[int, int] = {}
            if ids:
                id_bind = bindparam("ids", expanding=True)
                counts = connection.execute(
                    text(
                        "SELECT session_id, COUNT(*) AS sample_count FROM meter_values "
                        "WHERE measurand = :measurand AND session_id IN :ids "
                        "GROUP BY session_id"
                    ).bindparams(id_bind),
                    {"measurand": ENERGY_MEASURAND, "ids": ids},
                ).mappings().all()
                sample_counts = {
                    int(row["session_id"]): int(row["sample_count"]) for row in counts
                }
        grouped: dict[str, list[dict[str, Any]]] = {code: [] for code in codes}
        for row in session_rows:
            grouped[str(row["charge_point_code"])].append(dict(row))
        return {"sessions": grouped, "sample_counts": sample_counts}
    finally:
        engine.dispose()


def _render_comparisons(comparisons: list[Comparison]) -> None:
    print(
        "Mã trụ | transactionId | đầu Wh | cuối Wh | kWh đáp án | kWh hệ thống | "
        "ngắt | mẫu gửi/lưu | trạng thái | kết quả"
    )
    for row in comparisons:
        expected = f"{row.expected_kwh:.3f}" if row.expected_kwh is not None else "-"
        actual = f"{row.actual_kwh:.3f}" if row.actual_kwh is not None else "-"
        verdict = "OK" if row.ok else "LỖI: " + "; ".join(row.errors)
        print(
            f"{row.code} | {row.transaction_id or '-'} | {row.meter_start_wh} | "
            f"{row.meter_stop_wh if row.meter_stop_wh is not None else '-'} | "
            f"{expected} | {actual} | {row.disconnects} | "
            f"{row.samples_sent}/{row.samples_saved} | {row.status} | {verdict}"
        )
    passed = sum(row.ok for row in comparisons)
    print(f"{passed}/{len(comparisons)} phiên khớp")


def scenario_exit_code(comparisons: list[Comparison]) -> int:
    """Trả mã lỗi nếu bất kỳ phiên nào lệch đáp án."""
    return 0 if comparisons and all(item.ok for item in comparisons) else 1


def _reserve_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(url: str, process: subprocess.Popen, log_path: Path) -> None:
    deadline = time.monotonic() + 35
    http_scheme = "https://" if url.startswith("wss://") else "http://"
    host_path = url.removeprefix("wss://").removeprefix("ws://")
    health_url = http_scheme + host_path.split("/", maxsplit=1)[0] + "/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(log_path.read_text(encoding="utf-8", errors="replace"))
        try:
            with urllib.request.urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.2)
    raise TimeoutError(f"Server local không sẵn sàng; xem {log_path}")


def _seed_local_database(database_url: str, codes: tuple[str, ...]) -> str:
    """Tạo trạm, trụ, đầu nối và thẻ dùng riêng cho lần chạy này."""
    os.environ["DATABASE_URL"] = database_url
    os.environ["APP_ENV"] = "test"
    os.environ["CSMS_ENV_FILE"] = str(ROOT / ".env.example")
    os.environ["CSMS_LOCAL_SIMULATOR_ENABLED"] = "false"
    import app.models  # noqa: F401
    from app.database import SessionLocal
    from app.database import engine as scenario_engine
    from app.models.charge_point import ChargePoint, Connector
    from app.models.id_tag import IdTag
    from app.models.station import Station
    from app.models.user import Role, User

    id_tag = f"SIM{uuid.uuid4().hex[:17]}"
    try:
        with SessionLocal() as db:
            role = db.query(Role).filter_by(name="driver").first()
            if role is None:
                role = Role(name="driver")
                db.add(role)
                db.flush()
            driver = User(
                email=f"scenario-{uuid.uuid4().hex[:12]}@test.invalid",
                password_hash="scenario-only",
                full_name="Scenario Driver",
                is_active=True,
                roles=[role],
            )
            db.add(driver)
            db.flush()
            station = Station(
                name=f"Reconnect {uuid.uuid4().hex[:8]}",
                address="temporary scenario database",
                status="active",
                owner_id=driver.id,
            )
            db.add(station)
            db.flush()
            db.add(IdTag(id_tag=id_tag, user_id=driver.id, is_blocked=False))
            for code in codes:
                point = ChargePoint(code=code, station_id=station.id, status="offline")
                db.add(point)
                db.flush()
                db.add(Connector(charge_point_id=point.id, connector_id=1))
            db.commit()
    finally:
        scenario_engine.dispose()
    return id_tag


def _scenario_codes(seed: int, run: int, count: int) -> tuple[str, ...]:
    stamp = f"{seed % 100000:05d}{run:02d}"
    return tuple(f"RC{stamp}-{index:02d}" for index in range(count))


def _run_one_iteration(
    config: ScenarioConfig,
    ws_url: str,
    database_url: str,
    codes: tuple[str, ...],
    id_tag: str,
    run_seed: int,
) -> list[Comparison]:
    plans = build_plans(run_seed, len(codes), config.max_disconnects)
    master_rng = random.Random(run_seed)
    db_engine = create_engine(database_url)
    try:
        with db_engine.connect() as connection:
            baseline_session_id = int(connection.execute(
                text("SELECT COALESCE(MAX(id), 0) FROM charging_sessions")
            ).scalar_one())
    finally:
        db_engine.dispose()

    charger_seeds = [master_rng.randint(0, 2**31 - 1) for _ in codes]

    async def run_fleet() -> list[RunResult]:
        semaphore = asyncio.Semaphore(max(1, config.chargers))

        async def run_one(code: str, plan: ChargerPlan, charger_seed: int) -> RunResult:
            async with semaphore:
                return await _run_charger(
                    ws_url,
                    code,
                    id_tag,
                    plan,
                    random.Random(charger_seed),
                    samples=config.samples,
                    tick_seconds=config.tick_seconds,
                    boot_on_reconnect=config.boot_on_reconnect,
                )

        return await asyncio.gather(*(
            run_one(code, plan, charger_seed)
            for code, plan, charger_seed in zip(codes, plans, charger_seeds)
        ))

    started = time.monotonic()
    run_records = asyncio.run(run_fleet())
    snapshot = _database_snapshot(database_url, codes, baseline_session_id)
    comparisons = evaluate_results(
        run_records, snapshot["sessions"], snapshot["sample_counts"]
    )
    _render_comparisons(comparisons)
    print(f"seed={run_seed}; thời gian={time.monotonic() - started:.2f}s")
    return comparisons


def _run_local(config: ScenarioConfig) -> int:
    temp_directory = tempfile.TemporaryDirectory(prefix="csms-reconnect-")
    directory = Path(temp_directory.name)
    database_path = directory / "scenario.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    port = _reserve_port()
    ws_url = f"ws://127.0.0.1:{port}/ocpp"
    log_path = directory / "uvicorn.log"
    all_codes = tuple(
        code
        for run in range(1, config.repeats + 1)
        for code in _scenario_codes(config.seed, run, config.chargers)
    )
    env = os.environ.copy()
    env.update({
        "DATABASE_URL": database_url,
        "APP_ENV": "test",
        "CSMS_ENV_FILE": str(ROOT / ".env.example"),
        "CSMS_LOCAL_SIMULATOR_ENABLED": "false",
        "OCPP_JOB_POLL_SECONDS": "60",
        "PYTHONUTF8": "1",
    })
    log_file = log_path.open("w", encoding="utf-8")
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=BACKEND,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        _wait_for_server(ws_url, process, log_path)
        id_tag = _seed_local_database(database_url, all_codes)
        results: list[Comparison] = []
        for run in range(1, config.repeats + 1):
            run_codes = _scenario_codes(config.seed, run, config.chargers)
            run_seed = config.seed + run - 1
            print(f"\nLượt {run}/{config.repeats}, seed={run_seed}")
            results.extend(_run_one_iteration(
                config, ws_url, database_url, run_codes, id_tag, run_seed
            ))
        return scenario_exit_code(results)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        log_file.close()
        temp_directory.cleanup()


def _run_external(config: ScenarioConfig) -> int:
    if not config.database_url or not config.id_tag or len(config.codes) != config.chargers:
        raise ValueError(
            "Khi dùng server staging, cần --database-url, --id-tag và --codes đủ số trụ; "
            "hãy giới hạn --repeats 1."
        )
    if config.repeats != 1:
        raise ValueError("Với server ngoài, dùng --repeats 1 để không tạo nhiều phiên cho cùng bộ trụ.")
    comparisons = _run_one_iteration(
        config,
        config.server_url or "",
        config.database_url,
        config.codes,
        config.id_tag,
        config.seed,
    )
    return scenario_exit_code(comparisons)


def _parse_args(argv: list[str] | None = None) -> ScenarioConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chargers", type=int, default=20)
    parser.add_argument("--max-disconnects", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tick-seconds", type=float, default=0.2)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--server-url", help="WebSocket base, ví dụ ws://staging/ocpp")
    parser.add_argument("--database-url", help="DB chỉ đọc để đối chiếu trên staging")
    parser.add_argument("--codes", help="Mã trụ staging, phân cách dấu phẩy")
    parser.add_argument("--id-tag", help="ID thẻ test đã được staging cho phép")
    parser.add_argument(
        "--boot-on-reconnect", action=argparse.BooleanOptionalAction, default=True
    )
    args = parser.parse_args(argv)
    if args.chargers < 1 or args.max_disconnects < 1 or args.repeats < 1:
        parser.error("chargers, max-disconnects và repeats phải lớn hơn 0")
    if args.samples < args.max_disconnects + 1:
        parser.error("samples phải lớn hơn max-disconnects để ngắt giữa phiên")
    if args.tick_seconds < 0:
        parser.error("tick-seconds không được âm")
    codes = tuple(code.strip() for code in (args.codes or "").split(",") if code.strip())
    if args.server_url and not args.database_url:
        parser.error("server staging cần database-url để xác minh phiên và số đo")
    return ScenarioConfig(
        chargers=args.chargers,
        max_disconnects=args.max_disconnects,
        seed=args.seed,
        tick_seconds=args.tick_seconds,
        samples=args.samples,
        repeats=args.repeats,
        boot_on_reconnect=args.boot_on_reconnect,
        server_url=args.server_url,
        database_url=args.database_url,
        codes=codes,
        id_tag=args.id_tag,
    )


def main(argv: list[str] | None = None) -> int:
    config = _parse_args(argv)
    print(f"seed={config.seed} (các lượt tiếp theo tăng seed thêm 1)")
    try:
        if config.server_url:
            return _run_external(config)
        return _run_local(config)
    except Exception as exc:
        logger.exception("Kịch bản reconnect thất bại")
        print(f"LỖI: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
