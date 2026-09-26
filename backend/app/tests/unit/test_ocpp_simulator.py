import asyncio
import json

from app.dev_tools.ocpp_simulator.simulator import (
    SimpleSimulator,
    make_call,
    make_calleerror,
    make_callresult,
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
