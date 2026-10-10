import asyncio
import json

import pytest

from app.dev_tools.ocpp_simulator.simulator import (
    DEMO_POINT_PROFILES,
    SimpleSimulator,
    charge_point_uri,
    main,
    make_call,
    make_calleerror,
    make_callresult,
    run_fleet,
    simulator_codes,
)


def test_simulator_builds_well_formed_call_and_response_frames() -> None:
    call = make_call("BootNotification", {"chargePointVendor": "TestVendor"})
    call_id = call[1]

    assert call[0] == 2
    assert isinstance(call_id, str)
    assert call[2:] == ["BootNotification", {"chargePointVendor": "TestVendor"}]
    assert make_callresult(call_id, {"status": "Accepted"}) == [
        3,
        call_id,
        {"status": "Accepted"},
    ]
    assert make_calleerror(call_id, "NotSupported", "unsupported") == [
        4,
        call_id,
        "NotSupported",
        "unsupported",
        {},
    ]


def test_simulator_waits_for_matching_callresult() -> None:
    class FakeWebSocket:
        def __init__(self):
            self.sent = []

        async def send(self, message):
            self.sent.append(json.loads(message))

    async def scenario():
        simulator = SimpleSimulator()
        simulator.ws = FakeWebSocket()
        request_task = asyncio.create_task(
            simulator._call("StartTransaction", {"connectorId": 1})
        )
        await asyncio.sleep(0)
        request_id = simulator.ws.sent[0][1]
        simulator._pending_calls[request_id].set_result(
            {"transactionId": 42, "idTagInfo": {"status": "Accepted"}}
        )
        return await request_task

    assert asyncio.run(scenario()) == {
        "transactionId": 42,
        "idTagInfo": {"status": "Accepted"},
    }


def test_simulator_acknowledges_reset_and_requests_reconnect() -> None:
    class FakeWebSocket:
        def __init__(self):
            self.messages = iter(
                [json.dumps([2, "reset-1", "Reset", {"type": "Soft"}])]
            )
            self.sent = []

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.messages)
            except StopIteration:
                raise StopAsyncIteration from None

        async def send(self, message):
            self.sent.append(json.loads(message))

    async def scenario():
        simulator = SimpleSimulator()
        simulator.ws = FakeWebSocket()
        await simulator._receive_loop()
        return simulator

    simulator = asyncio.run(scenario())

    assert simulator.ws.sent == [[3, "reset-1", {"status": "Accepted"}]]
    assert simulator._reboot_requested is True
    assert simulator._disconnect_event.is_set()


def test_simulator_acknowledges_remote_start_transaction() -> None:
    class FakeWebSocket:
        def __init__(self):
            self.messages = iter(
                [
                    json.dumps(
                        [
                            2,
                            "remotestart-1",
                            "RemoteStartTransaction",
                            {"connectorId": 1, "idTag": "DEMO-DRIVER-0005"},
                        ]
                    )
                ]
            )
            self.sent = []

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.messages)
            except StopIteration:
                raise StopAsyncIteration from None

        async def send(self, message):
            self.sent.append(json.loads(message))

    async def scenario():
        simulator = SimpleSimulator()
        simulator.ws = FakeWebSocket()
        try:
            await asyncio.wait_for(simulator._receive_loop(), timeout=0.1)
        except (asyncio.TimeoutError, StopAsyncIteration):
            pass
        return simulator

    simulator = asyncio.run(scenario())
    assert [3, "remotestart-1", {"status": "Accepted"}] in simulator.ws.sent


def test_simulator_acknowledges_remote_stop_transaction() -> None:
    class FakeWebSocket:
        def __init__(self):
            self.messages = iter(
                [
                    json.dumps(
                        [
                            2,
                            "remotestop-1",
                            "RemoteStopTransaction",
                            {"transactionId": 100},
                        ]
                    )
                ]
            )
            self.sent = []

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.messages)
            except StopIteration:
                raise StopAsyncIteration from None

        async def send(self, message):
            self.sent.append(json.loads(message))

    async def scenario():
        simulator = SimpleSimulator()
        simulator.ws = FakeWebSocket()
        try:
            await asyncio.wait_for(simulator._receive_loop(), timeout=0.1)
        except (asyncio.TimeoutError, StopAsyncIteration):
            pass
        return simulator

    simulator = asyncio.run(scenario())
    assert [3, "remotestop-1", {"status": "Accepted"}] in simulator.ws.sent


@pytest.mark.parametrize("count", [1, 3, 20])
def test_fleet_uses_only_codes_seeded_by_the_server(count):
    from seed_data import SIMULATOR_CODES

    assert simulator_codes(count) == SIMULATOR_CODES[:count]


@pytest.mark.parametrize("count", [1, 3, 20])
def test_demo_station_fleet_uses_registered_codes_and_connector_inventory(count):
    from seed_data import SIMULATOR_CODES, STATIONS

    specs = {point["code"]: point for station in STATIONS for point in station["charge_points"]}
    expected = set(SIMULATOR_CODES[:count]) | (set(specs) - set(SIMULATOR_CODES))
    selected = simulator_codes(count, include_demo_stations=True)
    assert len(selected) == count + 5
    assert set(selected) == expected
    for code in selected:
        profile = SimpleSimulator(code=code).profile
        assert profile.connector_count == specs[code]["connectors"]
        assert (profile.vendor, profile.model) == (specs[code]["vendor"], specs[code]["model"])


@pytest.mark.parametrize("code, count, status, error", [
    ("SIM-01", 2, "Available", "NoError"),
    ("CP_VINCOM_01", 2, "Available", "NoError"),
    ("CP_VINCOM_02", 1, "Available", "NoError"),
    ("CP_AEON_01", 3, "Available", "NoError"),
    ("CP_AEON_FAULT", 1, "Faulted", "GroundFailure"),
    ("CP_DEMO_MAINT_01", 2, "Unavailable", "NoError"),
    ("TEST-01", 1, "Available", "NoError"),
])
def test_device_reports_every_declared_connector_and_preserves_demo_conditions(code, count, status, error):
    async def scenario():
        simulator = SimpleSimulator(code=code)
        sent = []

        async def call(action, payload=None):
            sent.append((action, payload))
            return {"status": "Accepted", "interval": 5} if action == "BootNotification" else {}

        simulator._call = call
        await simulator._run_loop()
        return sent

    sent = asyncio.run(scenario())
    assert sent[0][0] == "BootNotification"
    notifications = [payload for action, payload in sent if action == "StatusNotification"]
    assert [payload["connectorId"] for payload in notifications] == list(range(count + 1))
    assert all(payload["status"] == status and payload["errorCode"] == error for payload in notifications)


def test_cli_can_opt_into_demo_stations_without_changing_default_sim_count(monkeypatch):
    observed = []

    async def fleet(codes, server_url):
        observed.append((codes, server_url))

    monkeypatch.setattr("app.dev_tools.ocpp_simulator.simulator.run_fleet", fleet)
    main(["--count", "20", "--include-demo-stations", "true", "--server-url", "ws://app:8000/ocpp"])
    assert observed == [(simulator_codes(20) + tuple(DEMO_POINT_PROFILES), "ws://app:8000/ocpp")]


def test_cli_rejects_demo_station_selection_without_fleet(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["SIM-01", "--include-demo-stations", "true"])
    assert exc.value.code == 2
    assert "requires --count" in capsys.readouterr().err


@pytest.mark.parametrize("count", [-1, 0, 21])
def test_fleet_rejects_count_outside_registered_codes(count):
    with pytest.raises(ValueError, match="between 1 and 20"):
        simulator_codes(count)


@pytest.mark.parametrize("contents", ["", "SIM-01\nSIM-01", "CP-REAL-01", "SIM-../other"])
def test_fleet_rejects_empty_duplicate_or_real_codes(tmp_path, contents):
    codes_file = tmp_path / "seed_codes.txt"
    codes_file.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError, match="unique SIM-"):
        simulator_codes(1, codes_file)


@pytest.mark.parametrize("url, expected", [
    ("ws://app:8000/ocpp", "ws://app:8000/ocpp/SIM-01"),
    ("ws://app:8000/ocpp/", "ws://app:8000/ocpp/SIM-01"),
    ("ws://localhost:8123", "ws://localhost:8123/ocpp/SIM-01"),
    ("wss://example.test/csms/ocpp/", "wss://example.test/csms/ocpp/SIM-01"),
])
def test_simulator_uses_configured_server_address(url, expected):
    assert charge_point_uri(url, "SIM-01") == expected
    assert SimpleSimulator(code="SIM-01", server_url=url).uri == expected


@pytest.mark.parametrize("url", [
    "http://app:8000/ocpp", "ws:///ocpp", "ws://user:secret@app/ocpp",
    "ws://app/ocpp?token=secret", "ws://app/ocpp#fragment", "ws://app:70000/ocpp",
])
def test_simulator_rejects_invalid_server_address(url):
    with pytest.raises(ValueError):
        charge_point_uri(url, "SIM-01")


@pytest.mark.parametrize("argv", [["--count", "0"], ["--count", "21"], ["SIM-01", "--count", "2"]])
def test_cli_rejects_invalid_fleet_before_connecting(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
    assert "error:" in capsys.readouterr().err


def test_fleet_connects_concurrently_and_cleans_up_on_failure(monkeypatch):
    async def scenario():
        codes = simulator_codes(20)
        started = set()
        stopped = set()
        ready = asyncio.Event()

        async def connect(simulator):
            started.add(simulator.code)
            if len(started) == 20:
                ready.set()
            try:
                await ready.wait()
                if simulator.code == "SIM-20":
                    raise RuntimeError("device failed")
                await asyncio.Event().wait()
            finally:
                stopped.add(simulator.code)

        monkeypatch.setattr(SimpleSimulator, "connect", connect)
        with pytest.raises(RuntimeError, match="device failed"):
            await asyncio.wait_for(run_fleet(codes, "ws://app:8000/ocpp"), timeout=1)
        assert started == stopped == set(codes)

    asyncio.run(scenario())


def test_fleet_fails_if_one_connection_ends_and_cancels_the_rest(monkeypatch):
    async def scenario():
        stopped = set()

        async def connect(simulator):
            try:
                if simulator.code == "SIM-01":
                    return
                await asyncio.Event().wait()
            finally:
                stopped.add(simulator.code)

        monkeypatch.setattr(SimpleSimulator, "connect", connect)
        with pytest.raises(RuntimeError, match="SIM-01: connection ended"):
            await run_fleet(("SIM-01", "SIM-02"), "ws://app:8000/ocpp")
        assert stopped == {"SIM-01", "SIM-02"}

    asyncio.run(scenario())
@pytest.mark.parametrize("key,value,status", [
    ("HeartbeatInterval", "60", "Accepted"),
    ("MeterValueSampleInterval", "5", "Accepted"),
    ("HeartbeatInterval", "29", "Rejected"),
    ("MeterValueSampleInterval", "901", "Rejected"),
    ("MeterValueSampleInterval", "5.5", "Rejected"),
    ("UnknownSetting", "60", "NotSupported"),
])
def test_configuration_change_and_readback(key, value, status):
    async def scenario():
        sim = SimpleSimulator(code="SIM-01")
        original = dict(sim.configuration)
        replies = []

        class FakeWebSocket:
            def __aiter__(self):
                async def messages():
                    yield json.dumps([2, "change", "ChangeConfiguration", {
                        "key": key, "value": value,
                    }])
                    yield json.dumps([2, "read", "GetConfiguration", {
                        "key": [key],
                    }])
                return messages()

            async def send(self, message):
                replies.append(json.loads(message))

        sim.ws = FakeWebSocket()
        await sim._receive_loop()

        assert replies[0] == [3, "change", {"status": status}]
        if status == "Accepted":
            assert sim.configuration[key] == int(value)
            assert replies[1][2]["configurationKey"] == [{
                "key": key, "readonly": False, "value": value,
            }]
            assert replies[1][2]["unknownKey"] == []
        else:
            assert sim.configuration == original
            if key not in original:
                assert replies[1][2]["unknownKey"] == [key]

    asyncio.run(scenario())
def test_meter_interval_and_stop(monkeypatch):
    from app.dev_tools.ocpp_simulator import simulator as module

    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    async def scenario():
        sim = SimpleSimulator(code="SIM-01")
        sim.connected = True
        calls = []

        async def fake_call(action, payload=None):
            calls.append((action, payload))
            if action == "StartTransaction":
                return {
                    "transactionId": 73,
                    "idTagInfo": {"status": "Accepted"},
                }
            return {}

        sim._call = fake_call
        await sim._trigger_remote_start(2, "TEST")
        assert sim._active_transactions[2]["transaction_id"] == 73

        clock[0] = 29
        await sim.send_meter_values()
        assert not any(action == "MeterValues" for action, _ in calls)

        sim.configuration["MeterValueSampleInterval"] = 5
        await sim.send_meter_values()
        meters = [payload for action, payload in calls if action == "MeterValues"]
        assert len(meters) == 1
        assert meters[0]["connectorId"] == 2
        assert meters[0]["transactionId"] == 73
        sample = meters[0]["meterValue"][0]["sampledValue"][0]
        assert sample["value"] == "1100"
        assert sample["unit"] == "Wh"

        await sim._trigger_remote_stop(73)
        assert sim._active_transactions == {}
        clock[0] = 60
        await sim.send_meter_values()
        assert sum(action == "MeterValues" for action, _ in calls) == 1

    asyncio.run(scenario())