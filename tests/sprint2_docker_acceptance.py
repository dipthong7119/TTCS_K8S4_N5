"""T-01/T-19/T-27/T-55: isolated Compose checks, also run by existing CI.

This filename is deliberately outside default pytest discovery: Docker checks
require docker-compose.acceptance.yml to be running. No application logic is
used by the simulated charge point or the HTTP/WebSocket clients.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from collections import deque
from contextlib import AsyncExitStack, suppress
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import websockets
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def docker_stack(request):
    project = request.config.getoption("--docker-project")
    command = ["docker", "compose", "--env-file", str(ROOT / ".env.example"),
               "-p", project, "-f", str(ROOT / "docker-compose.acceptance.yml")]

    def compose(*arguments, timeout=60, environment=None):
        result = subprocess.run(command + list(arguments), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout, check=False,
                                env=None if environment is None else {**os.environ, **environment})
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout.strip()

    app_port = compose("port", "app", "8000").rsplit(":", 1)[1]
    db_port = compose("port", "db", "5432").rsplit(":", 1)[1]
    url = f"http://127.0.0.1:{app_port}"
    engine = create_engine(f"postgresql+psycopg2://csms_acceptance:acceptance_only@127.0.0.1:{db_port}/csms_acceptance")
    try:
        assert httpx.get(f"{url}/health", timeout=5).status_code == 200
        yield {"http": url, "ws": url.replace("http://", "ws://") + "/ocpp", "db": engine, "compose": compose}
    finally:
        compose("rm", "-sf", "simulator")
        engine.dispose()


async def call(socket, action, payload=None):
    message_id = uuid4().hex
    await socket.send(json.dumps([2, message_id, action, payload or {}]))
    response = json.loads(await asyncio.wait_for(socket.recv(), timeout=5))
    assert response[:2] == [3, message_id], response
    return response[2]


@pytest.mark.asyncio
async def test_t43_t45_t53_postgres_offline_session_recovers_with_late_stop(docker_stack):
    """Real PostgreSQL + WebSocket + background job; manual oracle = 12.345 kWh."""
    code = f"SPRINT3-{uuid4().hex[:10]}"
    with docker_stack["db"].begin() as db:
        tag = db.execute(text(
            "SELECT id_tags.id_tag FROM id_tags JOIN users ON users.id=id_tags.user_id "
            "WHERE users.email='driver@csms.local' AND id_tags.is_blocked=FALSE LIMIT 1"
        )).scalar_one()
        station_id = db.execute(text("SELECT station_id FROM charge_points WHERE code='SIM-19'")).scalar_one()
        point_id = db.execute(text(
            "INSERT INTO charge_points (code, station_id, status) VALUES (:code, :station, 'offline') RETURNING id"
        ), {"code": code, "station": station_id}).scalar_one()
        db.execute(text(
            "INSERT INTO connectors (charge_point_id, connector_id, status, error_code) VALUES (:id, 1, 'unknown', 'NoError')"
        ), {"id": point_id})

    async def boot():
        socket = await websockets.connect(f"{docker_stack['ws']}/{code}", subprotocols=["ocpp1.6"])
        assert (await call(socket, "BootNotification", {"chargePointVendor": "Acceptance", "chargePointModel": "Sprint3"}))["status"] == "Accepted"
        return socket

    socket = await boot()
    async with socket:
        start = await call(socket, "StartTransaction", {
            "connectorId": 1, "idTag": tag, "meterStart": 18340, "timestamp": "2026-10-01T08:00:00Z",
        })
        assert start["idTagInfo"]["status"] == "Accepted"
        transaction_id = start["transactionId"]
        for timestamp, value in [
            ("2026-10-01T08:01:00Z", "19340"),
            ("2026-10-01T08:00:30Z", "18380"),
            ("2026-10-01T08:01:00Z", "19340"),
        ]:
            assert await call(socket, "MeterValues", {
                "connectorId": 1, "transactionId": transaction_id,
                "meterValue": [{"timestamp": timestamp, "sampledValue": [{"value": value, "unit": "Wh"}]}],
            }) == {}
        with docker_stack["db"].connect() as db:
            assert db.execute(text("SELECT value FROM meter_values WHERE session_id=:id"), {"id": transaction_id}).scalars().all() == [19340]
        warnings = [line for line in docker_stack["compose"]("logs", "--no-color", "app").splitlines()
                    if f"Meter value rejected: cp={code} session={transaction_id} " in line]
        assert len(warnings) == 1

    async with asyncio.timeout(5):
        while True:
            with docker_stack["db"].connect() as db:
                status = db.execute(text("SELECT status FROM charge_points WHERE code=:code"), {"code": code}).scalar_one()
            if status == "offline":
                break
            await asyncio.sleep(0.05)
    with docker_stack["db"].begin() as db:
        db.execute(text("UPDATE charge_points SET last_seen_at=CURRENT_TIMESTAMP-INTERVAL '61 seconds' WHERE code=:code"), {"code": code})
    async with asyncio.timeout(5):
        while True:
            with docker_stack["db"].connect() as db:
                row = db.execute(text("SELECT status, ended_at FROM charging_sessions WHERE id=:id"), {"id": transaction_id}).one()
            if row.status == "anomaly":
                assert row.ended_at is None
                break
            await asyncio.sleep(0.05)

    async with httpx.AsyncClient(base_url=docker_stack["http"]) as client:
        assert (await client.post("/api/auth/login", json={"email": "operator@csms.local", "password": "Operator@2024!"})).status_code == 200
        anomalies = (await client.get("/api/sessions/anomalies", params={"days": "all", "reason": "offline"})).json()
        assert transaction_id in [item["id"] for item in anomalies["items"]]
        socket = await boot()
        async with socket:
            await call(socket, "StatusNotification", {"connectorId": 1, "status": "Available", "errorCode": "NoError"})
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
            message_id = uuid4().hex
            raw = json.dumps([2, message_id, "StopTransaction", payload])
            await socket.send(raw)
            first = json.loads(await asyncio.wait_for(socket.recv(), timeout=5))
            assert first == [3, message_id, {"idTagInfo": {"status": "Accepted"}}]
            await socket.send(raw)
            assert json.loads(await asyncio.wait_for(socket.recv(), timeout=5)) == first
            assert (await call(socket, "StopTransaction", {**payload, "meterStop": 99999}))["idTagInfo"]["status"] == "Accepted"
        detail = (await client.get(f"/api/sessions/{transaction_id}")).json()
        assert detail["status"] == "completed"
        assert detail["meter_stop_wh"] == 30685
        assert detail["kwh"] == 12.345
        assert detail["ended_at"] == "2026-10-01T08:03:00Z"
        anomalies = (await client.get("/api/sessions/anomalies", params={"days": "all"})).json()
        assert transaction_id not in [item["id"] for item in anomalies["items"]]
        with docker_stack["db"].connect() as db:
            values = db.execute(text("SELECT value FROM meter_values WHERE session_id=:id ORDER BY measured_at"), {"id": transaction_id}).scalars().all()
            assert values == [19340, 26340, 30685]
            count = db.execute(text("SELECT COUNT(*) FROM charging_sessions WHERE charge_point_code=:code"), {"code": code}).scalar_one()
            assert count == 1


def test_postgres_migration_roundtrip(docker_stack):
    # Each existing migration test gets its own schema, leaving the app intact.
    result = subprocess.run(
        [sys.executable,
         "-m", "pytest", str(ROOT / "tests/test_migrations.py"), "-q", "--tb=short",
         "--migration-database-url", docker_stack["db"].url.render_as_string(hide_password=False)],
        cwd=ROOT / "backend", capture_output=True, text=True, timeout=90, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout.strip())


def test_device_container_clock_five_hours_ahead_uses_database_time(docker_stack):
    # TZ alone changes local wall time, so this intentionally faulty independent
    # device labels that local time as UTC, producing a true five-hour payload skew.
    client = '''
import asyncio, json, time
from datetime import datetime
from uuid import uuid4
import websockets
time.tzset()
assert datetime.now().astimezone().utcoffset().total_seconds() == 18000
async def main():
    async with websockets.connect('ws://app:8000/ocpp/SIM-01', subprotocols=['ocpp1.6']) as socket:
        for action, payload in [
            ('BootNotification', {'chargePointVendor':'Clock test','chargePointModel':'Independent'}),
            ('StatusNotification', {'connectorId':1,'status':'Available','errorCode':'NoError','timestamp':datetime.now().isoformat()+'Z'}),
            ('Heartbeat', {'timestamp':datetime.now().isoformat()+'Z'}),
        ]:
            message_id = uuid4().hex
            await socket.send(json.dumps([2,message_id,action,payload]))
            frame = json.loads(await socket.recv())
            assert frame[:2] == [3,message_id], frame
            if action == 'BootNotification': assert frame[2]['status'] == 'Accepted'
        print('Device clock offset: +5h; server UTC: ' + frame[2]['currentTime'])
asyncio.run(main())
'''
    output = docker_stack["compose"]("run", "--rm", "--no-deps", "simulator", "python", "-c", client)
    with docker_stack["db"].connect() as db:
        delta = db.execute(text("SELECT EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP-last_seen_at)) FROM charge_points WHERE code='SIM-01'")).scalar_one()
    assert 0 <= delta < 2, f"last_seen_at differs from the database clock by {delta}s"
    print(f"{output}; database clock delta={delta:.3f}s")


@pytest.mark.asyncio
async def test_50_connections_with_live_sse_on_postgres(docker_stack, request):
    duration = request.config.getoption("--sprint2-soak-seconds")
    async with httpx.AsyncClient(base_url=docker_stack["http"], timeout=15) as client:
        login = await client.post("/api/auth/login", json={"email": "owner@csms.local", "password": "Owner@2024!"})
        assert login.status_code == 200
        station = await client.post("/api/stations", json={"name": f"Load {uuid4().hex[:8]}", "address": "Acceptance only", "status": "active"})
        assert station.status_code == 201, station.text
        station_id = station.json()["id"]
        codes = [f"LOAD-{uuid4().hex[:8]}-{number:02d}" for number in range(50)]
        for code in codes:
            response = await client.post("/api/charge-points", json={"code": code, "station_id": station_id, "connector_count": 4})
            assert response.status_code == 201, response.text

        async def connect(code):
            socket = await websockets.connect(f"{docker_stack['ws']}/{code}", subprotocols=["ocpp1.6"])
            try:
                boot = await call(socket, "BootNotification", {})
                assert boot["status"] == "Accepted" and boot["interval"] == 5
                return socket
            except BaseException:
                await socket.close()
                raise

        async with AsyncExitStack() as stack:
            # Register each connection for cleanup even if a later Boot fails.
            sockets = []
            for code in codes:
                sockets.append(await stack.enter_async_context(await connect(code)))
            async with client.stream("GET", "/api/monitoring/sse") as response:
                assert response.status_code == 200
                events = deque(maxlen=100)

                async def drain_sse():
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            event = json.loads(line[6:])
                            if event.get("station_id") == station_id:
                                events.append(event)

                reader = asyncio.create_task(drain_sse())
                started = time.monotonic()
                rounds = 0
                next_report = 60
                try:
                    while True:
                        await asyncio.gather(*(call(socket, "Heartbeat") for socket in sockets))
                        rounds += 1
                        if time.monotonic() - started >= next_report:
                            print(f"Docker soak: {time.monotonic()-started:.0f}s, {rounds} rounds, 50 sockets and SSE active", flush=True)
                            next_report += 60
                        if time.monotonic() - started >= duration:
                            break
                        await asyncio.sleep(min(2, max(0, duration - (time.monotonic() - started))))
                    changed = time.monotonic()
                    await call(sockets[0], "StatusNotification", {"connectorId": 1, "status": "Charging", "errorCode": "NoError"})
                    async with asyncio.timeout(1):
                        while not any(point["code"] == codes[0] and point["connectors"][0]["status"] == "bận" for event in events for point in event.get("charge_points", [])):
                            await asyncio.sleep(0.01)
                    latency = time.monotonic() - changed
                    began_query = time.monotonic()
                    tree = await client.get("/api/monitoring/tree")
                    assert tree.status_code == 200
                    points = next(item for item in tree.json() if item["id"] == station_id)["charge_points"]
                    assert len(points) == 50 and all(point["status"] == "online" for point in points)
                    assert sum(len(point["connectors"]) for point in points) == 200
                    print(f"50 PostgreSQL-backed sockets + SSE: {time.monotonic()-started:.1f}s, {rounds} rounds, 200 connectors, SSE={latency:.3f}s, tree HTTP={time.monotonic()-began_query:.3f}s")
                finally:
                    reader.cancel()
                    with suppress(asyncio.CancelledError):
                        await reader


def test_simulator_container_stop_start_three_times(docker_stack):
    compose = docker_stack["compose"]
    dependencies = {service: compose("ps", "-q", service) for service in ("app", "db")}

    def wait_for_state(status, connector_status, timeout):
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            with docker_stack["db"].connect() as db:
                row = db.execute(text("SELECT cp.status,c.status FROM charge_points cp JOIN connectors c ON c.charge_point_id=cp.id WHERE cp.code='SIM-01' AND c.connector_id=1")).one()
            if row == (status, connector_status):
                return
            time.sleep(0.1)
        pytest.fail(f"SIM-01 did not become {status}/{connector_status}: {row}")

    try:
        for cycle in range(3):
            # The fixture already started app/db. Recreating dependencies here
            # can erase the tmpfs database and invalidate the cached DB port.
            compose("--profile", "ocpp-simulator", "up", "-d", "--no-build", "--no-deps", "simulator")
            for service, container in dependencies.items():
                assert compose("ps", "-q", service) == container, f"Starting simulator recreated {service}"
            wait_for_state("online", "rảnh", 15)
            compose("stop", "-t", "1", "simulator")
            # Also verify it remains offline after two negotiated 5s intervals.
            time.sleep(11)
            wait_for_state("offline", "unknown", 2)
            compose("start", "simulator")
            wait_for_state("online", "rảnh", 15)
            print(f"Container stop/start cycle {cycle+1}/3 passed")
    finally:
        compose("rm", "-sf", "simulator")


def test_failed_candidate_leaves_previous_container_healthy(docker_stack):
    """T-03: validate isolation with real Docker, in addition to shell-path tests."""
    compose = docker_stack["compose"]
    old_container = compose("ps", "-q", "app")
    candidate = f"csms-acceptance-candidate-{uuid4().hex[:8]}"
    try:
        compose("run", "-d", "--no-deps", "--name", candidate, "app", "sh", "-c", "exit 42")
        result = subprocess.run(["docker", "wait", candidate], capture_output=True, text=True, timeout=10, check=False)
        assert result.returncode == 0 and result.stdout.strip() == "42"
        assert compose("ps", "-q", "app") == old_container
        assert httpx.get(f"{docker_stack['http']}/health", timeout=3).status_code == 200
        assert httpx.get(f"{docker_stack['http']}/", follow_redirects=True, timeout=3).status_code == 200
    finally:
        subprocess.run(["docker", "rm", "-f", candidate], capture_output=True, text=True, timeout=10, check=False)


@pytest.mark.parametrize("count", [1, 3, 20])
def test_t55_configured_fleet_online_in_monitoring_within_one_minute(docker_stack, count):
    compose = docker_stack["compose"]
    expected = {f"SIM-{number:02d}" for number in range(1, count + 1)}
    dependencies = {service: compose("ps", "-q", service) for service in ("app", "db")}
    with docker_stack["db"].connect() as db:
        registered = dict(db.execute(text("SELECT code,id FROM charge_points WHERE code LIKE 'SIM-%'")).all())
        previous_message_id = db.execute(text("SELECT COALESCE(MAX(id),0) FROM ocpp_messages")).scalar_one()
    assert len(registered) == 20 and expected <= registered.keys()

    with httpx.Client(base_url=docker_stack["http"], timeout=5) as client:
        login = client.post("/api/auth/login", json={"email": "owner@csms.local", "password": "Owner@2024!"})
        assert login.status_code == 200

        def online_codes():
            response = client.get("/api/monitoring/tree")
            assert response.status_code == 200, response.text
            return {point["code"] for station in response.json() for point in station["charge_points"]
                    if point["code"].startswith("SIM-") and point["status"] == "online"}

        def wait_for(expected_codes, deadline):
            while time.monotonic() < deadline:
                observed = online_codes()
                if observed == expected_codes:
                    return
                time.sleep(0.1)
            pytest.fail(f"Expected {sorted(expected_codes)}, observed {sorted(observed)}")

        # Previous test sizes must be offline before measuring the new fleet.
        wait_for(set(), time.monotonic() + 15)
        try:
            started = time.monotonic()
            compose("--profile", "ocpp-simulator", "up", "-d", "--no-build", "--no-deps", "simulator",
                    environment={"CSMS_SIMULATOR_COUNT": str(count), "CSMS_SIMULATOR_URL": "ws://app:8000/ocpp/"})
            wait_for(expected, started + 60)
            elapsed = time.monotonic() - started
            assert elapsed < 60
            for service, container in dependencies.items():
                assert compose("ps", "-q", service) == container, f"Starting fleet recreated {service}"
            # The negotiated heartbeat is 5s; verify connections stay online.
            time.sleep(6)
            assert online_codes() == expected
            assert len(compose("ps", "-q", "simulator").splitlines()) == 1
            with docker_stack["db"].connect() as db:
                assert dict(db.execute(text("SELECT code,id FROM charge_points WHERE code LIKE 'SIM-%'")).all()) == registered
                heartbeats = set(db.execute(text(
                    "SELECT DISTINCT charge_point_code FROM ocpp_messages "
                    "WHERE action='Heartbeat' AND id>:previous_id AND charge_point_code LIKE 'SIM-%'"
                ), {"previous_id": previous_message_id}).scalars())
                assert heartbeats == expected, f"Missing fleet Heartbeats: {sorted(expected - heartbeats)}"
            print(f"T-55: {count} seeded points online in monitoring API after {elapsed:.3f}s; heartbeat maintained; app/db unchanged")
        finally:
            compose("rm", "-sf", "simulator")


def test_t55_demo_stations_report_all_registered_connectors(docker_stack):
    compose = docker_stack["compose"]
    expected = {f"SIM-{number:02d}": (2, "Available", "NoError") for number in range(1, 21)}
    expected.update({
        "CP_VINCOM_01": (2, "Available", "NoError"),
        "CP_VINCOM_02": (1, "Available", "NoError"),
        "CP_AEON_01": (3, "Available", "NoError"),
        "CP_AEON_FAULT": (1, "Faulted", "GroundFailure"),
        "CP_DEMO_MAINT_01": (2, "Unavailable", "NoError"),
    })
    dependencies = {service: compose("ps", "-q", service) for service in ("app", "db")}
    with docker_stack["db"].connect() as db:
        registered = dict(db.execute(text("SELECT code,id FROM charge_points")).all())
        previous_message_id = db.execute(text("SELECT COALESCE(MAX(id),0) FROM ocpp_messages")).scalar_one()
    assert set(expected) <= set(registered)

    with httpx.Client(base_url=docker_stack["http"], timeout=5) as client:
        login = client.post("/api/auth/login", json={"email": "admin@csms.local", "password": "Admin@2024!"})
        assert login.status_code == 200

        def read_points():
            result = client.get("/api/monitoring/tree")
            assert result.status_code == 200, result.text
            return {point["code"]: point for station in result.json() for point in station["charge_points"]
                    if point["code"] in expected}

        def matches_inventory(points):
            return set(points) == set(expected) and all(
                points[code]["status"] == "online"
                and len(points[code]["connectors"]) == count
                and {item["connector_id"] for item in points[code]["connectors"]} == set(range(1, count + 1))
                and all(item["ocpp_status"] == status and item["error_code"] == error
                        for item in points[code]["connectors"])
                for code, (count, status, error) in expected.items()
            )

        try:
            compose("--profile", "ocpp-simulator", "up", "-d", "--no-build", "--no-deps", "simulator",
                    environment={"CSMS_SIMULATOR_COUNT": "20", "CSMS_SIMULATOR_INCLUDE_DEMO_STATIONS": "true",
                                 "CSMS_SIMULATOR_URL": "ws://app:8000/ocpp"})
            deadline = time.monotonic() + 60
            points = read_points()
            while not matches_inventory(points) and time.monotonic() < deadline:
                time.sleep(0.1)
                points = read_points()
            assert matches_inventory(points), points
            assert sum(len(point["connectors"]) for point in points.values()) == 49
            time.sleep(6)
            assert matches_inventory(read_points())
            for service, container in dependencies.items():
                assert compose("ps", "-q", service) == container
            with docker_stack["db"].connect() as db:
                assert dict(db.execute(text("SELECT code,id FROM charge_points")).all()) == registered
                heartbeats = set(db.execute(text(
                    "SELECT DISTINCT charge_point_code FROM ocpp_messages WHERE action='Heartbeat' AND id>:previous_id"
                ), {"previous_id": previous_message_id}).scalars())
                assert heartbeats == set(expected)
            result = client.post("/api/charge_points/CP_AEON_FAULT/reset", json={"type": "Soft"})
            assert result.status_code == 200, result.text
            deadline = time.monotonic() + 15
            time.sleep(1.5)
            while not matches_inventory(read_points()) and time.monotonic() < deadline:
                time.sleep(0.1)
            assert matches_inventory(read_points()), "Reset must preserve the seeded fault/maintenance profiles"
            print("T-55: all 25 seeded points online, 49 connectors reported, fault/maintenance preserved after Reset")
        finally:
            compose("rm", "-sf", "simulator")
