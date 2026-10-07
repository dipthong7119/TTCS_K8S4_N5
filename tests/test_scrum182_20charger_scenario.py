"""SCRUM-182: Kịch bản tự động 20 trụ ảo ngắt-nối ngẫu nhiên, kiểm kWh cuối.

Tác giả  : Vy Hoàng Tú (SCRUM-182)
Review   : Hoàng Văn Đức (SCRUM-183 sẽ dùng output JSON của test này)

Mục tiêu (theo AC của S-21 và E-04):
- Khởi chạy 20 trụ SIM- song song qua docker-compose.acceptance.yml.
- Mỗi trụ chạy ít nhất 1 phiên hoàn chỉnh:
    StartTransaction -> gửi MeterValues nhiều lần -> StopTransaction
- Một số trụ ngắt kết nối giữa chừng rồi nối lại (mô phỏng ngoại tuyến).
- Sau khi tất cả phiên kết thúc, kiểm tra DB:
    * Mọi phiên bình thường có energy_kwh > 0.
    * kWh trong DB khớp (trong sai số 0.001 kWh) với tổng MeterValues gửi.
    * Không có phiên nào còn trạng thái "active" sau StopTransaction.
- Xuất kết quả dạng JSON để SCRUM-183 (Đức) đối chiếu.

Chạy thủ công:
    docker compose --env-file .env.example `
        -p csms-scrum182 -f docker-compose.acceptance.yml `
        up -d --build --wait db app

    .venv/Scripts/python.exe -m pytest tests/test_scrum182_20charger_scenario.py --docker-project csms-scrum182 -v -s

    docker compose --env-file .env.example `
        -p csms-scrum182 -f docker-compose.acceptance.yml `
        down -v --remove-orphans
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import websockets
from sqlalchemy import create_engine, text

# ─────────────────────────────────────────────────────────────────────────────
# Hằng số kịch bản
# ─────────────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]

# Số trụ ảo (có thể override bằng env SCRUM182_CHARGER_COUNT)
CHARGER_COUNT = int(os.getenv("SCRUM182_CHARGER_COUNT", "20"))

# Số trụ sẽ ngắt kết nối giữa phiên (mặc định 5/20 = 25%)
DISCONNECT_COUNT = int(os.getenv("SCRUM182_DISCONNECT_COUNT", "5"))

# MeterValues gửi mỗi phiên (mỗi lần tăng METER_STEP_WH watt-giờ)
METER_READINGS_PER_SESSION = int(os.getenv("SCRUM182_METER_READINGS", "4"))
METER_STEP_WH = int(os.getenv("SCRUM182_METER_STEP_WH", "2500"))  # 2.5 kWh/lần

# Timeout tối đa để chờ một phiên đóng trong DB (giây)
SESSION_CLOSE_TIMEOUT = int(os.getenv("SCRUM182_SESSION_CLOSE_TIMEOUT", "30"))
RANDOM_SEED = int(os.getenv("SCRUM182_RANDOM_SEED", "42"))
DISCONNECT_MIN = int(os.getenv("SCRUM182_DISCONNECT_MIN", "1"))
DISCONNECT_MAX = int(os.getenv("SCRUM182_DISCONNECT_MAX", "1"))

# File JSON kết quả — SCRUM-183 (Đức) sẽ đọc file này để đối chiếu
RESULT_JSON_PATH = Path(os.getenv("SCRUM182_RESULT_PATH", str(ROOT / "ketqua" / "scrum182_kwh_result.json")))

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Fixture: Docker stack
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def docker_stack(request):
    """Kết nối tới stack đang chạy (db + app).

    Stack phải được khởi động thủ công trước khi chạy test:
        docker compose --env-file .env.example \
            -p csms-scrum182 -f docker-compose.acceptance.yml \
            up -d --build --wait db app
    """
    import subprocess

    project = request.config.getoption("--docker-project")
    command = [
        "docker", "compose",
        "--env-file", str(ROOT / ".env.example"),
        "-p", project,
        "-f", str(ROOT / "docker-compose.acceptance.yml"),
    ]

    def compose(*arguments, timeout: int = 60, environment=None):
        result = subprocess.run(
            command + list(arguments),
            capture_output=True, text=True,
            timeout=timeout, check=False,
            env=None if environment is None else {**os.environ, **environment},
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout.strip()

    app_port = compose("port", "app", "8000").rsplit(":", 1)[1]
    db_port  = compose("port", "db",  "5432").rsplit(":", 1)[1]
    http_url = f"http://127.0.0.1:{app_port}"
    ws_url   = f"ws://127.0.0.1:{app_port}/ocpp"
    engine   = create_engine(
        f"postgresql+psycopg2://csms_acceptance:acceptance_only"
        f"@127.0.0.1:{db_port}/csms_acceptance",
        future=True,
    )

    # Kiểm tra stack đang chạy
    resp = httpx.get(f"{http_url}/health", timeout=5)
    assert resp.status_code == 200, f"App chua chay: {resp.status_code}"

    try:
        with engine.connect() as connection:
            id_tag = connection.execute(
                text(
                    "SELECT tags.id_tag FROM id_tags tags "
                    "JOIN users ON users.id = tags.user_id "
                    "WHERE users.email = :email AND tags.is_blocked = false "
                    "AND (tags.expiry_date IS NULL OR tags.expiry_date > CURRENT_TIMESTAMP) "
                    "ORDER BY tags.id LIMIT 1"
                ),
                {"email": "driver@csms.local"},
            ).scalar_one_or_none()
        assert id_tag, "Acceptance seed did not create a valid driver RFID tag"
        yield {"http": http_url, "ws": ws_url, "db": engine, "id_tag": id_tag}
    finally:
        engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# Helper OCPP client nhỏ gọn (không import logic server)
# ─────────────────────────────────────────────────────────────────────────────

class _OCPPClient:
    """Client OCPP 1.6J tối giản cho một trụ ảo."""

    def __init__(self, ws_base: str, code: str):
        self.code = code
        self.uri  = f"{ws_base}/{code}"
        self._ws  = None
        self._pending: dict[str, asyncio.Future] = {}
        self._recv_task: asyncio.Task | None = None
        self.session_records: list[dict] = []

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            self.uri,
            subprotocols=["ocpp1.6"],
            open_timeout=10,
        )
        self._recv_task = asyncio.create_task(self._recv_loop())

    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
        if self._recv_task and not self._recv_task.done():
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                logger.debug("Cancelled OCPP receiver for %s", self.code)
            except Exception:
                logger.exception("OCPP receiver failed while disconnecting %s", self.code)
        self._ws = None

    async def _recv_loop(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if not isinstance(msg, list) or len(msg) < 3:
                    continue
                msg_type = msg[0]
                msg_id   = str(msg[1])
                if msg_type == 3:  # CALLRESULT
                    fut = self._pending.get(msg_id)
                    if fut and not fut.done():
                        fut.set_result(msg[2])
                elif msg_type == 4:  # CALLERROR
                    fut = self._pending.get(msg_id)
                    if fut and not fut.done():
                        fut.set_exception(RuntimeError(f"OCPP {msg[2]}: {msg[3]}"))
                elif msg_type == 2:  # CALL từ server
                    _, srv_id, action, _payload = msg
                    await self._handle_server_call(srv_id, action)
        except websockets.ConnectionClosed:
            logger.debug("OCPP connection closed for %s", self.code)
        except Exception as exc:
            logger.exception("OCPP receive failed for %s", self.code)
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(exc)
        finally:
            for fut in self._pending.values():
                if not fut.done():
                    fut.cancel()

    async def _handle_server_call(self, msg_id: str, action: str) -> None:
        if action in ("RemoteStopTransaction", "Reset"):
            resp = [3, msg_id, {"status": "Accepted"}]
        else:
            resp = [4, msg_id, "NotImplemented", f"{action} not handled", {}]
        if self._ws:
            await self._ws.send(json.dumps(resp))

    async def call(self, action: str, payload: dict | None = None,
                   timeout: float = 10.0) -> dict:
        msg_id = uuid.uuid4().hex
        frame  = [2, msg_id, action, payload or {}]
        loop   = asyncio.get_running_loop()
        fut    = loop.create_future()
        self._pending[msg_id] = fut
        try:
            await self._ws.send(json.dumps(frame))
            return await asyncio.wait_for(fut, timeout=timeout)
        finally:
            self._pending.pop(msg_id, None)

    async def boot(self) -> dict:
        return await self.call("BootNotification", {
            "chargePointVendor": "SCRUM182-Vendor",
            "chargePointModel":  "SCRUM182-Model",
            "firmwareVersion":   "1.0.0",
        })

    async def status_notification(self, connector_id: int, status: str) -> None:
        await self.call("StatusNotification", {
            "connectorId": connector_id,
            "status":      status,
            "errorCode":   "NoError",
            "timestamp":   _utc_now(),
        })

    async def start_transaction(self, id_tag: str, meter_start_wh: int = 0) -> dict:
        return await self.call("StartTransaction", {
            "idTag":       id_tag,
            "connectorId": 1,
            "meterStart":  meter_start_wh,
            "timestamp":   _utc_now(),
        })

    async def meter_values(self, transaction_id: int, wh_value: float) -> None:
        await self.call("MeterValues", {
            "connectorId":   1,
            "transactionId": transaction_id,
            "meterValue": [{
                "timestamp": _utc_now(),
                "sampledValue": [{
                    "value":     str(round(wh_value, 3)),
                    "measurand": "Energy.Active.Import.Register",
                    "unit":      "Wh",
                }],
            }],
        })

    async def stop_transaction(self, transaction_id: int, meter_stop_wh: int,
                               reason: str = "EVDisconnected") -> dict:
        return await self.call("StopTransaction", {
            "transactionId": transaction_id,
            "meterStop":     meter_stop_wh,
            "timestamp":     _utc_now(),
            "reason":        reason,
        })


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ─────────────────────────────────────────────────────────────────────────────
# Kịch bản một trụ
# ─────────────────────────────────────────────────────────────────────────────

async def _run_one_charger(
    ws_base: str,
    code: str,
    *,
    do_disconnect: bool,
    id_tag: str,
    meter_readings: int,
    meter_step_wh: int,
    rng: random.Random,
    disconnect_count: int = 1,
) -> dict:
    """
    Chạy một trụ ảo qua vòng đời hoàn chỉnh.
    Trả về dict ghi lại kết quả để đối chiếu (SCRUM-183).
    """
    record: dict = {
        "code":                code,
        "id_tag":              id_tag,
        "do_disconnect":       do_disconnect,
        "disconnect_count":    0,
        "meter_readings_sent": [],
        "meter_start_wh":      0,
        "meter_stop_wh":       None,
        "expected_kwh":        None,
        "transaction_id":      None,
        "error":               None,
    }

    client = _OCPPClient(ws_base, code)
    try:
        disconnect_after = set(rng.sample(range(meter_readings - 1), disconnect_count)) if do_disconnect else set()
        # 1. Kết nối + BootNotification
        await client.connect()
        boot_result = await client.boot()
        assert boot_result.get("status") == "Accepted", \
            f"{code}: BootNotification bi tu choi: {boot_result}"

        # 2. StatusNotification
        for cid in (0, 1):
            await client.status_notification(cid, "Available")

        # 3. StartTransaction
        meter_start = rng.randint(0, 1000)
        record["meter_start_wh"] = meter_start
        start_result = await client.start_transaction(id_tag, meter_start_wh=meter_start)
        assert start_result.get("idTagInfo", {}).get("status") in ("Accepted", "ConcurrentTx"), \
            f"{code}: StartTransaction bi tu choi: {start_result}"
        transaction_id = start_result.get("transactionId") or start_result.get("idTagInfo", {}).get("transactionId")
        assert transaction_id, f"{code}: khong co transactionId"
        record["transaction_id"] = transaction_id

        await client.status_notification(1, "Charging")

        # 4. Gửi MeterValues từng bước
        current_wh = float(meter_start)
        for reading_idx in range(meter_readings):
            current_wh += meter_step_wh + rng.uniform(-100, 100)
            current_wh  = round(current_wh, 3)
            await client.meter_values(transaction_id, current_wh)
            record["meter_readings_sent"].append(current_wh)

            # Nối lại đúng transactionId; không tạo StartTransaction thứ hai.
            if reading_idx in disconnect_after:
                await client.disconnect()
                await asyncio.sleep(rng.uniform(0.5, 1.5))
                # Kết nối lại và boot lại
                await client.connect()
                await client.boot()
                await client.status_notification(0, "Available")
                await client.status_notification(1, "Charging")
                record["disconnect_count"] += 1

        # 5. StopTransaction
        meter_stop = int(current_wh)
        record["meter_stop_wh"] = meter_stop
        await client.stop_transaction(transaction_id, meter_stop)

        # 6. Trở về Available
        await client.status_notification(1, "Available")

        # kWh kỳ vọng: (meter_stop - meter_start) / 1000
        expected_kwh = round((meter_stop - meter_start) / 1000.0, 3)
        record["expected_kwh"] = expected_kwh

    except Exception as exc:
        record["error"] = str(exc)
    finally:
        await client.disconnect()

    return record


# ─────────────────────────────────────────────────────────────────────────────
# Đăng ký trụ trong hệ thống
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_chargers_registered(http_url: str, codes: list[str]) -> int:
    """Đăng ký station + chargers nếu chưa tồn tại. Trả về station_id."""
    with httpx.Client(base_url=http_url, timeout=15) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": "owner@csms.local", "password": "Owner@2024!"},
        )
        assert login.status_code == 200, f"Dang nhap that bai: {login.text}"

        station_name = f"SCRUM182-Station-{uuid.uuid4().hex[:6]}"
        station_resp = client.post("/api/stations", json={
            "name":    station_name,
            "address": "SCRUM-182 Test Only",
            "status":  "active",
        })
        assert station_resp.status_code == 201, station_resp.text
        station_id = station_resp.json()["id"]

        for code in codes:
            cp_resp = client.post("/api/charge-points", json={
                "code":            code,
                "station_id":      station_id,
                "connector_count": 1,
            })
            # 409 = đã tồn tại -> bỏ qua
            assert cp_resp.status_code in (201, 409), \
                f"Khong dang ky duoc {code}: {cp_resp.text}"

    return station_id


# ─────────────────────────────────────────────────────────────────────────────
# Kiểm tra DB
# ─────────────────────────────────────────────────────────────────────────────

def _wait_sessions_closed(engine, transaction_ids: list[int],
                          timeout: int = 30, *, allow_incomplete: bool = False) -> dict[int, dict]:
    """Chờ đến khi tất cả phiên có ended_at != NULL trong DB."""
    result = {}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, status, energy_kwh, ended_at "
                    "FROM charging_sessions "
                    "WHERE id = ANY(:ids)"
                ),
                {"ids": transaction_ids},
            ).mappings().all()
        result = {row["id"]: dict(row) for row in rows}
        all_closed = len(result) == len(set(transaction_ids)) and all(
            row["ended_at"] is not None for row in result.values()
        )
        if all_closed:
            return result
        time.sleep(0.5)
    if allow_incomplete:
        return result
    pytest.fail(
        f"Timeout {timeout}s — cac phien chua dong: "
        + str([tid for tid in transaction_ids
               if result.get(tid, {}).get("ended_at") is None])
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test chính — SCRUM-182
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scrum182_20_chargers_random_disconnect_kwh_integrity(docker_stack):
    """
    SCRUM-182: 20 trụ ảo chạy song song, một số ngắt-nối ngẫu nhiên.
    Kiểm tra tính toàn vẹn kWh cuối phiên.

    Kết quả xuất ra ketqua/scrum182_kwh_result.json
    để SCRUM-183 (Đức) dùng làm nguồn đối chiếu.
    """
    assert 1 <= DISCONNECT_MIN <= DISCONNECT_MAX < METER_READINGS_PER_SESSION
    rng = random.Random(RANDOM_SEED)
    codes = [f"SCRUM182-SIM-{i:02d}" for i in range(1, CHARGER_COUNT + 1)]

    # Chọn ngẫu nhiên các trụ sẽ ngắt kết nối
    disconnect_set = set(rng.sample(codes, min(DISCONNECT_COUNT, len(codes))))

    # 1. Đăng ký trụ trong hệ thống
    station_id = _ensure_chargers_registered(docker_stack["http"], codes)
    with docker_stack["db"].connect() as connection:
        previous_session_id = connection.execute(text("SELECT COALESCE(MAX(id), 0) FROM charging_sessions")).scalar_one()
    print(f"\n[SCRUM-182] Station ID: {station_id}, Charger count: {len(codes)}, "
          f"Disconnect set: {sorted(disconnect_set)}")

    # 2. Chạy tất cả trụ song song
    tasks = [
        _run_one_charger(
            docker_stack["ws"],
            code,
            do_disconnect=(code in disconnect_set),
            id_tag=docker_stack["id_tag"],
            meter_readings=METER_READINGS_PER_SESSION,
            meter_step_wh=METER_STEP_WH,
            rng=random.Random(rng.randint(0, 2**31)),
            disconnect_count=rng.randint(DISCONNECT_MIN, DISCONNECT_MAX),
        )
        for code in codes
    ]

    print(f"[SCRUM-182] Khoi chay {len(tasks)} tru song song...")
    t_start = time.monotonic()
    records = await asyncio.gather(*tasks)
    elapsed = time.monotonic() - t_start
    print(f"[SCRUM-182] Tat ca tru hoan thanh sau {elapsed:.2f}s")

    # Luôn xuất kết quả cả khi lỗi để CI giữ bằng chứng theo mã phiên.
    transaction_ids = [r["transaction_id"] for r in records if r.get("transaction_id")]
    db_rows = _wait_sessions_closed(
        docker_stack["db"], transaction_ids, timeout=SESSION_CLOSE_TIMEOUT, allow_incomplete=True
    ) if transaction_ids else {}
    with docker_stack["db"].connect() as connection:
        sessions = connection.execute(text(
            "SELECT id, charge_point_code FROM charging_sessions "
            "WHERE id > :previous_id AND charge_point_code = ANY(:codes)"
        ), {"previous_id": previous_session_id, "codes": codes}).mappings().all()
        samples = connection.execute(text(
            "SELECT session_id, value FROM meter_values WHERE session_id = ANY(:ids) "
            "AND measurand = 'Energy.Active.Import.Register' ORDER BY measured_at, id"
        ), {"ids": transaction_ids}).mappings().all()

    # 5. So sánh kWh kỳ vọng vs DB
    mismatches   = []
    result_items = []

    for rec in records:
        tid = rec["transaction_id"]
        db_row       = db_rows.get(tid, {})
        db_kwh       = float(db_row.get("energy_kwh") or 0)
        expected_kwh = rec["expected_kwh"] or 0.0
        delta        = abs(db_kwh - expected_kwh)
        db_samples = [float(sample["value"]) for sample in samples if sample["session_id"] == tid]
        session_ids = [row["id"] for row in sessions if row["charge_point_code"] == rec["code"]]
        faults = []
        if rec["error"]:
            faults.append(rec["error"])
        if session_ids != [tid]:
            faults.append(f"lost/duplicate session: expected [{tid}], got {session_ids}")
        if db_row.get("ended_at") is None or db_row.get("status") != "completed":
            faults.append(f"session not completed: status={db_row.get('status')}")
        if db_samples != rec["meter_readings_sent"]:
            faults.append(f"MeterValues lost/duplicated: expected {rec['meter_readings_sent']}, got {db_samples}")
        if expected_kwh <= 0 or db_kwh <= 0 or delta > 0.001:
            faults.append(f"kWh mismatch: expected={expected_kwh:.3f}, actual={db_kwh:.3f}, delta={delta:.6f}")
        ok = not faults

        result_items.append({
            "code":                  rec["code"],
            "transaction_id":        tid,
            "do_disconnect":         rec["do_disconnect"],
            "disconnect_count":      rec["disconnect_count"],
            "id_tag":                rec["id_tag"],
            "meter_start_wh":        rec["meter_start_wh"],
            "meter_stop_wh":         rec["meter_stop_wh"],
            "meter_readings_sent":   rec["meter_readings_sent"],
            "expected_kwh":          expected_kwh,
            "db_kwh":                db_kwh,
            "db_status":             db_row.get("status"),
            "kwh_delta":             round(delta, 6),
            "kwh_ok":                ok,
            "errors":                faults,
        })

        if not ok:
            mismatches.append(
                f"  {rec['code']} session={tid}: ky_vong={expected_kwh:.3f} kWh, "
                f"DB={db_kwh:.3f} kWh, delta={delta:.6f}: {'; '.join(faults)}"
            )
        print(f"SESSION {tid} {rec['code']} expected={expected_kwh:.3f} kWh "
              f"actual={db_kwh:.3f} kWh delta={delta:.6f} reconnects={rec['disconnect_count']} "
              f"{'PASS' if ok else 'FAIL'} {'; '.join(faults)}")

    # 6. Xuất JSON để SCRUM-183 đối chiếu
    RESULT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    result_payload = {
        "scrum_task":                 "SCRUM-182",
        "random_seed":                RANDOM_SEED,
        "generated_at":               _utc_now(),
        "charger_count":              CHARGER_COUNT,
        "disconnect_count":           DISCONNECT_COUNT,
        "meter_readings_per_session": METER_READINGS_PER_SESSION,
        "meter_step_wh":              METER_STEP_WH,
        "total_elapsed_s":            round(elapsed, 2),
        "items":                      result_items,
        "summary": {
            "total":        len(result_items),
            "kwh_ok":       sum(1 for it in result_items if it["kwh_ok"]),
            "kwh_mismatch": len(mismatches),
            "all_passed":   len(mismatches) == 0,
        },
    }
    RESULT_JSON_PATH.write_text(
        json.dumps(result_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[SCRUM-182] Ket qua JSON xuat tai: {RESULT_JSON_PATH}")
    print(f"[SCRUM-182] Tong: {len(result_items)} phien | "
          f"OK: {result_payload['summary']['kwh_ok']} | "
          f"Loi: {len(mismatches)}")

    # 7. Assert cuối cùng
    assert not mismatches, (
        f"kWh khong khop giua tru gui va DB ({len(mismatches)} tru):\n"
        + "\n".join(mismatches)
        + f"\n\nXem chi tiet: {RESULT_JSON_PATH}"
    )

    still_active = [it for it in result_items if it["db_status"] == "active"]
    assert not still_active, (
        f"Van con {len(still_active)} phien o trang thai 'active' sau StopTransaction: "
        + str([it["code"] for it in still_active])
    )

    print(
        f"\n[SCRUM-182] ALL {CHARGER_COUNT} SESSIONS VALID — "
        f"kWh khop, khong phien nao con 'active'. ({elapsed:.2f}s)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test: 3 trụ, không ngắt (CI khung nhỏ - T-56 Thanh Tùng)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scrum182_smoke_3_chargers(docker_stack):
    """
    Smoke test: 3 trụ, không ngắt kết nối.
    Dùng cho bước CI khung nhỏ (T-56). Thanh Tùng có thể chạy test này
    trước khi kịch bản 20 trụ hoàn chỉnh sẵn sàng.
    """
    rng   = random.Random(99)
    codes = [f"SCRUM182-SMOKE-{i:02d}" for i in range(1, 4)]

    _ensure_chargers_registered(docker_stack["http"], codes)

    tasks = [
        _run_one_charger(
            docker_stack["ws"], code,
            do_disconnect=False,
            id_tag=docker_stack["id_tag"],
            meter_readings=2,
            meter_step_wh=1000,
            rng=random.Random(rng.randint(0, 2**31)),
        )
        for code in codes
    ]
    records = await asyncio.gather(*tasks)

    errors = [(r["code"], r["error"]) for r in records if r.get("error")]
    assert not errors, "Smoke test — loi tru:\n" + "\n".join(f"  {c}: {e}" for c, e in errors)

    tids = [r["transaction_id"] for r in records if r.get("transaction_id")]
    db_rows = _wait_sessions_closed(docker_stack["db"], tids, timeout=20)

    for rec in records:
        tid    = rec["transaction_id"]
        db_row = db_rows.get(tid, {})
        assert db_row.get("energy_kwh") is not None and float(db_row["energy_kwh"]) > 0, \
            f"Smoke {rec['code']}: energy_kwh khong hop le trong DB: {db_row}"

    print("\n[SCRUM-182 Smoke] 3/3 tru — kWh hop le trong DB")
