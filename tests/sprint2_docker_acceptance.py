"""T-01/T-19/T-27: opt-in checks of the isolated Compose stack, also run by CI.

This filename is deliberately outside default pytest discovery: Docker checks
require docker-compose.acceptance.yml to be running. No application logic is
used by the simulated charge point or the HTTP/WebSocket clients.
"""

import asyncio
import json
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

    def compose(*arguments, timeout=60):
        result = subprocess.run(command + list(arguments), capture_output=True, text=True, timeout=timeout, check=False)
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
