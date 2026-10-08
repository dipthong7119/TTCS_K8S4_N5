"""T-12/T-15/T-27/T-29/T-31: exercise a real isolated HTTP/WebSocket server."""

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import time
from contextlib import AsyncExitStack, closing, contextmanager
from pathlib import Path

import httpx
import pytest
import websockets


@contextmanager
def sqlite_connection(path):
    # sqlite3's own context manager commits/rolls back but does not close.
    with closing(sqlite3.connect(path)) as connection, connection:
        yield connection


@pytest.fixture(scope="module")
def network_server(tmp_path_factory, unused_tcp_port_factory):
    backend = Path(__file__).resolve().parents[1] / "backend"
    directory = tmp_path_factory.mktemp("ocpp_network")
    database = directory / "network.db"
    port = unused_tcp_port_factory()
    env = os.environ.copy()
    env.update({
        "DATABASE_URL": f"sqlite:///{database.as_posix()}",
        "APP_ENV": "test",
        "CSMS_ENV_FILE": str(backend.parent / ".env.example"),
        "OCPP_HEARTBEAT_INTERVAL_SECONDS": "5",
        "OCPP_JOB_POLL_SECONDS": "1",
        "OCPP_REMOTE_CALL_TIMEOUT_SECONDS": "1",
        "SESSION_OFFLINE_GRACE_SECONDS": "60",
        "PYTHONUTF8": "1",
    })
    log = (directory / "server.log").open("w", encoding="utf-8")
    process = None

    def start():
        nonlocal process
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=backend, env=env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        for _ in range(150):
            if process.poll() is not None:
                raise RuntimeError((directory / "server.log").read_text(encoding="utf-8"))
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
        raise RuntimeError("The isolated server did not become healthy")

    def stop():
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    try:
        start()
        with sqlite_connection(database) as db:
            owner = db.execute("SELECT id FROM users WHERE email='owner@csms.local'").fetchone()[0]
            station_id = db.execute(
                "INSERT INTO stations(name,address,status,owner_id) VALUES('Network test','Test','active',?)", (owner,)
            ).lastrowid
            for index in range(50):
                point_id = db.execute(
                    "INSERT INTO charge_points(code,station_id) VALUES(?,?)", (f"NET-{index:02d}", station_id)
                ).lastrowid
                db.executemany(
                    "INSERT INTO connectors(charge_point_id,connector_id) VALUES(?,?)",
                    [(point_id, number) for number in range(1, 5)],
                )
        yield {"http": f"http://127.0.0.1:{port}", "ws": f"ws://127.0.0.1:{port}/ocpp",
               "database": database, "log": directory / "server.log",
               "restart": lambda: (stop(), start())}
    finally:
        stop()
        log.close()


async def call(socket, message_id, action, payload):
    await socket.send(json.dumps([2, message_id, action, payload]))
    response = json.loads(await asyncio.wait_for(socket.recv(), timeout=5))
    assert response[0] == 3, response
    assert response[1] == message_id
    return response


async def connect(server, code):
    socket = await websockets.connect(f"{server['ws']}/{code}", subprotocols=["ocpp1.6"])
    result = await call(socket, f"boot-{time.monotonic_ns()}", "BootNotification", {})
    assert result[2]["status"] == "Accepted"
    assert result[2]["interval"] == 5
    return socket


async def start_network_session(server, socket, meter_start=18340):
    with sqlite_connection(server["database"]) as db:
        tag = db.execute(
            "SELECT id_tags.id_tag FROM id_tags JOIN users ON users.id=id_tags.user_id "
            "WHERE users.email='driver@csms.local' AND id_tags.is_blocked=0 LIMIT 1"
        ).fetchone()[0]
    response = await call(socket, "start-network-session", "StartTransaction", {
        "connectorId": 1, "idTag": tag, "meterStart": meter_start, "timestamp": "2026-10-01T08:00:00Z",
    })
    assert response[2]["idTagInfo"]["status"] == "Accepted"
    return response[2]["transactionId"]


@pytest.mark.asyncio
async def test_t43_new_old_duplicate_samples_over_real_websocket(network_server):
    """T-43: mới → cũ → trùng, chỉ giữ số đo mới và đúng một cảnh báo."""
    socket = await connect(network_server, "NET-07")
    async with socket:
        transaction_id = await start_network_session(network_server, socket)
        for message_id, timestamp, value in [
            ("meter-new", "2026-10-01T08:03:00Z", "30685"),
            ("meter-old", "2026-10-01T08:02:00Z", "26340"),
            ("meter-duplicate", "2026-10-01T08:03:00Z", "30685"),
        ]:
            response = await call(socket, message_id, "MeterValues", {
                "connectorId": 1, "transactionId": transaction_id,
                "meterValue": [{"timestamp": timestamp, "sampledValue": [{"value": value, "unit": "Wh"}]}],
            })
            assert response == [3, message_id, {}]
        with sqlite_connection(network_server["database"]) as db:
            rows = db.execute("SELECT measured_at, value FROM meter_values WHERE session_id=?", (transaction_id,)).fetchall()
            assert rows == [("2026-10-01 08:03:00.000000", 30685)]
        warnings = [line for line in network_server["log"].read_text(encoding="utf-8").splitlines()
                    if "Meter value rejected: cp=NET-07 " in line]
        assert len(warnings) == 1
        assert "old_at=2026-10-01T08:03:00" in warnings[0]
        assert "new_at=2026-10-01T08:02:00" in warnings[0]


@pytest.mark.asyncio
async def test_t45_t53_offline_job_and_late_stop_over_real_websocket(network_server):
    """T-45/T-53: job thật → API bất thường → nối lại → Stop muộn → rời danh sách."""
    socket = await connect(network_server, "NET-08")
    async with socket:
        transaction_id = await start_network_session(network_server, socket)
        await call(socket, "meter-before-offline", "MeterValues", {
            "connectorId": 1, "transactionId": transaction_id,
            "meterValue": [{"timestamp": "2026-10-01T08:01:00Z",
                            "sampledValue": [{"value": "19340", "unit": "Wh"}]}],
        })
    # Advance only this isolated device's last-contact age, instead of sleeping a minute.
    async with asyncio.timeout(5):
        while True:
            with sqlite_connection(network_server["database"]) as db:
                offline = db.execute("SELECT status FROM charge_points WHERE code='NET-08'").fetchone()[0] == "offline"
            if offline:
                break
            await asyncio.sleep(0.05)
    with sqlite_connection(network_server["database"]) as db:
        db.execute("UPDATE charge_points SET last_seen_at=datetime('now','-61 seconds') WHERE code='NET-08'")
    async with asyncio.timeout(5):
        while True:
            with sqlite_connection(network_server["database"]) as db:
                state = db.execute("SELECT status, ended_at, meter_stop_wh FROM charging_sessions WHERE id=?", (transaction_id,)).fetchone()
            if state[0] == "anomaly":
                assert state[1:] == (None, None)
                break
            await asyncio.sleep(0.05)

    async with httpx.AsyncClient(base_url=network_server["http"]) as client:
        assert (await client.post("/api/auth/login", json={"email": "operator@csms.local", "password": "Operator@2024!"})).status_code == 200
        anomalies = (await client.get("/api/sessions/anomalies", params={"days": "all", "reason": "offline"})).json()
        assert transaction_id in [row["id"] for row in anomalies["items"]]
        socket = await connect(network_server, "NET-08")
        async with socket:
            await call(socket, "available-after-reconnect", "StatusNotification", {"connectorId": 1, "status": "Available", "errorCode": "NoError"})
            payload = {"transactionId": transaction_id, "meterStop": 30685,
                       "timestamp": "2026-10-01T15:03:00+07:00", "reason": "PowerLoss",
                       "transactionData": [
                           {"timestamp": timestamp, "sampledValue": [{"value": value, "unit": "Wh"}]}
                           for timestamp, value in [
                               ("2026-10-01T08:03:00Z", "30685"),
                               ("2026-10-01T08:01:00Z", "19340"),
                               ("2026-10-01T08:02:00Z", "26340"),
                               ("2026-10-01T08:02:00Z", "26340"),
                           ]
                       ]}
            first = await call(socket, "late-stop-network", "StopTransaction", payload)
            assert first[2]["idTagInfo"]["status"] == "Accepted"
            assert await call(socket, "late-stop-network", "StopTransaction", payload) == first
            await call(socket, "late-stop-different-id", "StopTransaction", {**payload, "meterStop": 99999})
        detail = (await client.get(f"/api/sessions/{transaction_id}")).json()
        assert detail["status"] == "completed"
        assert detail["meter_stop_wh"] == 30685
        assert detail["kwh"] == 12.345
        assert detail["ended_at"] == "2026-10-01T08:03:00Z"
        assert detail["anomaly_reason"] is None
        anomalies = (await client.get("/api/sessions/anomalies", params={"days": "all"})).json()
        assert transaction_id not in [row["id"] for row in anomalies["items"]]
        with sqlite_connection(network_server["database"]) as db:
            assert db.execute("SELECT COUNT(*) FROM charging_sessions WHERE charge_point_code='NET-08'").fetchone()[0] == 1
            rows = db.execute("SELECT value FROM meter_values WHERE session_id=? ORDER BY measured_at", (transaction_id,)).fetchall()
            assert rows == [(19340,), (26340,), (30685,)]


@pytest.mark.asyncio
async def test_50_real_connections_with_heartbeat_and_200_connectors(network_server, request):
    duration = request.config.getoption("--sprint2-soak-seconds")
    async with AsyncExitStack() as stack:
        sockets = await asyncio.gather(*(connect(network_server, f"NET-{index:02d}") for index in range(50)))
        for socket in sockets:
            await stack.enter_async_context(socket)
        started = time.monotonic()
        rounds = 0
        while True:
            await asyncio.gather(*(call(socket, f"hb-{rounds}-{index}", "Heartbeat", {}) for index, socket in enumerate(sockets)))
            rounds += 1
            if time.monotonic() - started >= duration:
                break
            await asyncio.sleep(min(2, duration - (time.monotonic() - started)))
        async with httpx.AsyncClient(base_url=network_server["http"]) as client:
            login = await client.post("/api/auth/login", json={"email": "admin@csms.local", "password": "Admin@2024!"})
            assert login.status_code == 200
            tree = (await client.get("/api/monitoring/tree")).json()
            points = [point for station in tree for point in station["charge_points"]]
            assert len(points) == 50
            assert all(point["status"] == "online" for point in points)
            assert sum(len(point["connectors"]) for point in points) == 200
        print(f"50 OCPP sockets remained online for {time.monotonic() - started:.1f}s; {rounds} heartbeat rounds")


@pytest.mark.asyncio
async def test_real_duplicate_connection_and_malformed_frames(network_server):
    old = await connect(network_server, "NET-00")
    try:
        new = await connect(network_server, "NET-00")
        async with new:
            with pytest.raises(websockets.ConnectionClosed):
                await asyncio.wait_for(old.recv(), timeout=1)
            cases = [
                ("{}", "FormationViolation"),
                ("[]", "FormationViolation"),
                ('[2,"bad"]', "FormationViolation"),
                ('[9,"bad",{}]', "ProtocolError"),
                ('[2,"bad","Heartbeat",[]]', "FormationViolation"),
                ('[2,"bad","Unsupported",{}]', "NotImplemented"),
            ]
            for index, (raw, error) in enumerate(cases):
                await new.send(raw)
                frame = json.loads(await asyncio.wait_for(new.recv(), timeout=1))
                assert frame[0] == 4 and frame[2] == error
                await call(new, f"after-bad-{index}", "Heartbeat", {})
    finally:
        await old.close()


@pytest.mark.asyncio
async def test_real_offline_reconnect_three_times(network_server):
    for index in range(3):
        socket = await connect(network_server, "NET-01")
        async with socket:
            await call(socket, f"status-{index}", "StatusNotification", {"connectorId": 1, "status": "Charging", "errorCode": "NoError"})
        async with asyncio.timeout(1):
            while True:
                with sqlite_connection(network_server["database"]) as db:
                    state = db.execute("SELECT status FROM charge_points WHERE code='NET-01'").fetchone()[0]
                    connector = db.execute("SELECT status FROM connectors WHERE charge_point_id=(SELECT id FROM charge_points WHERE code='NET-01') AND connector_id=1").fetchone()[0]
                if state == "offline" and connector == "unknown":
                    break
                await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_persisted_response_survives_real_process_restart(network_server):
    socket = await connect(network_server, "NET-02")
    async with socket:
        original = await call(socket, "durable-id", "Heartbeat", {})
        for _ in range(5):
            assert await call(socket, "durable-id", "Heartbeat", {}) == original
    network_server["restart"]()
    socket = await connect(network_server, "NET-02")
    async with socket:
        assert await call(socket, "durable-id", "Heartbeat", {}) == original
    with sqlite_connection(network_server["database"]) as db:
        assert db.execute("SELECT COUNT(*) FROM ocpp_messages WHERE charge_point_code='NET-02' AND msg_id='durable-id'").fetchone()[0] == 1


@pytest.mark.asyncio
async def test_unknown_point_is_rejected_within_one_second_and_logged_once(network_server):
    started = time.monotonic()
    with pytest.raises(websockets.exceptions.InvalidHandshake):
        async with asyncio.timeout(1):
            await websockets.connect(f"{network_server['ws']}/NET-UNKNOWN", subprotocols=["ocpp1.6"])
    assert time.monotonic() - started < 1
    lines = network_server["log"].read_text(encoding="utf-8", errors="replace").splitlines()
    warnings = [line for line in lines if "Rejected unknown charge point: code=NET-UNKNOWN" in line]
    assert len(warnings) == 1 and "ip=127.0.0.1" in warnings[0]


@pytest.mark.asyncio
async def test_real_sse_delivers_connector_change_within_one_second(network_server):
    socket = await connect(network_server, "NET-03")
    async with socket, httpx.AsyncClient(base_url=network_server["http"]) as client:
        assert (await client.post("/api/auth/login", json={"email": "owner@csms.local", "password": "Owner@2024!"})).status_code == 200
        async with client.stream("GET", "/api/monitoring/sse") as response:
            assert response.status_code == 200

            async def next_data():
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        return json.loads(line[6:])

            event = asyncio.create_task(next_data())
            started = time.monotonic()
            await call(socket, "sse-status", "StatusNotification", {"connectorId": 1, "status": "Charging", "errorCode": "NoError"})
            snapshot = await asyncio.wait_for(event, timeout=1)
            assert time.monotonic() - started < 1
            point = next(item for item in snapshot["charge_points"] if item["code"] == "NET-03")
            assert point["connectors"][0]["status"] == "bận"


@pytest.mark.asyncio
async def test_real_authorize_covers_valid_blocked_expired_unknown_and_paused_station(network_server):
    with sqlite_connection(network_server["database"]) as db:
        driver = db.execute("SELECT id FROM users WHERE email='driver@csms.local'").fetchone()[0]
        db.executemany(
            "INSERT INTO id_tags(id_tag,user_id,is_blocked,expiry_date) VALUES(?,?,?,?)",
            [("NET-VALID", driver, False, None), ("NET-BLOCK", driver, True, None),
             ("NET-EXPIRED", driver, False, "2000-01-01 00:00:00")],
        )
    socket = await connect(network_server, "NET-04")
    async with socket:
        for tag, expected in [("NET-VALID", "Accepted"), ("NET-BLOCK", "Blocked"), ("NET-EXPIRED", "Expired"), ("NET-MISSING", "Invalid")]:
            frame = await call(socket, f"auth-{tag}", "Authorize", {"idTag": tag})
            assert frame[2]["idTagInfo"]["status"] == expected
        try:
            with sqlite_connection(network_server["database"]) as db:
                db.execute("UPDATE stations SET status='inactive' WHERE name='Network test'")
            frame = await call(socket, "auth-inactive", "Authorize", {"idTag": "NET-VALID"})
            assert frame[2]["idTagInfo"]["status"] == "Blocked"
        finally:
            with sqlite_connection(network_server["database"]) as db:
                db.execute("UPDATE stations SET status='active' WHERE name='Network test'")


@pytest.mark.asyncio
async def test_real_reset_correlation_nonblocking_timeout_and_audit(network_server):
    socket = await connect(network_server, "NET-05")
    async with socket, httpx.AsyncClient(base_url=network_server["http"]) as client:
        assert (await client.post("/api/auth/login", json={"email": "operator@csms.local", "password": "Operator@2024!"})).status_code == 200
        task = asyncio.create_task(client.post("/api/charge_points/NET-05/reset", json={"type": "Soft"}))
        frame = json.loads(await asyncio.wait_for(socket.recv(), timeout=1))
        assert frame[0] == 2 and frame[2:] == ["Reset", {"type": "Soft"}]
        # Another HTTP request continues while Reset waits on its own future.
        assert (await client.get("/health")).status_code == 200
        await socket.send(json.dumps([3, "unmatched-reset", {"status": "Accepted"}]))
        await socket.send(json.dumps([3, frame[1], {"status": "Accepted"}]))
        response = await asyncio.wait_for(task, timeout=1)
        assert response.status_code == 200, response.text
        audit_response = await client.get("/api/audit", params={"charge_point_code": "NET-05"})
        assert audit_response.status_code == 200, audit_response.text
        audit = audit_response.json()
        assert audit["total"] == 1
        entry = audit["items"][0]
        assert entry["action"] == "charge_point.reset.accepted"
        assert entry["charge_point_code"] == "NET-05"
        assert entry["actor_email"] == "operator@csms.local"
        assert entry["details"] == {"reset_type": "Soft", "outcome": "Accepted"}
        assert entry["created_at"]
        with sqlite_connection(network_server["database"]) as db:
            assert db.execute("SELECT status FROM charge_points WHERE code='NET-05'").fetchone()[0] == "offline"
        assert (await client.post("/api/charge_points/NET-05/reset", json={"type": "Soft"})).status_code == 409

        await call(socket, "reset-recovery", "Heartbeat", {})
        started = time.monotonic()
        task = asyncio.create_task(client.post("/api/charge_points/NET-05/reset", json={"type": "Soft"}))
        frame = json.loads(await asyncio.wait_for(socket.recv(), timeout=1))
        assert frame[2] == "Reset"
        response = await task
        assert response.status_code == 504 and 0.8 <= time.monotonic() - started < 3
        audit = (await client.get("/api/audit", params={"charge_point_code": "NET-05"})).json()
        assert audit["total"] == 2
        assert [entry["action"] for entry in audit["items"]] == [
            "charge_point.reset.failed", "charge_point.reset.accepted",
        ]
        assert audit["items"][0]["details"] == {"reset_type": "Soft", "outcome": "timeout"}
        await call(socket, "after-reset-timeout", "Heartbeat", {})
        with sqlite_connection(network_server["database"]) as db:
            actions = db.execute("SELECT action FROM audit_logs WHERE charge_point_code='NET-05' ORDER BY id").fetchall()
            assert actions == [("charge_point.reset.accepted",), ("charge_point.reset.failed",)]


@pytest.mark.asyncio
async def test_real_heartbeat_deadline_and_recovery_with_socket_still_open(network_server):
    socket = await connect(network_server, "NET-06")
    async with socket:
        await call(socket, "before-deadline", "StatusNotification", {"connectorId": 1, "status": "Charging"})
        started = time.monotonic()
        async with asyncio.timeout(13):
            while True:
                with sqlite_connection(network_server["database"]) as db:
                    state = db.execute("SELECT status FROM charge_points WHERE code='NET-06'").fetchone()[0]
                    connector = db.execute("SELECT status FROM connectors WHERE charge_point_id=(SELECT id FROM charge_points WHERE code='NET-06') AND connector_id=1").fetchone()[0]
                if state == "offline":
                    assert connector == "unknown"
                    break
                await asyncio.sleep(0.2)
        assert 8 <= time.monotonic() - started < 13
        await call(socket, "after-deadline", "Heartbeat", {})
        with sqlite_connection(network_server["database"]) as db:
            assert db.execute("SELECT status FROM charge_points WHERE code='NET-06'").fetchone()[0] == "online"
            assert db.execute("SELECT status FROM connectors WHERE charge_point_id=(SELECT id FROM charge_points WHERE code='NET-06') AND connector_id=1").fetchone()[0] == "unknown"
        await call(socket, "fresh-after-deadline", "StatusNotification", {"connectorId": 1, "status": "Available"})
        with sqlite_connection(network_server["database"]) as db:
            assert db.execute("SELECT status FROM connectors WHERE charge_point_id=(SELECT id FROM charge_points WHERE code='NET-06') AND connector_id=1").fetchone()[0] == "rảnh"
