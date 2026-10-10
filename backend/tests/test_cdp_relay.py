import asyncio

import pytest

from backend.cdp_relay import CdpRelay, RelayError


class FakeWebSocket:
    def __init__(self):
        self.incoming = asyncio.Queue()
        self.sent = asyncio.Queue()
        self.closed = False

    async def receive_text(self):
        value = await self.incoming.get()
        if value is None:
            raise RuntimeError("disconnected")
        return value

    async def send_text(self, value):
        await self.sent.put(value)

    async def close(self, code=1000):
        self.closed = True
        await self.incoming.put(None)


@pytest.mark.asyncio
async def test_relay_forwards_only_frames_for_one_approved_session():
    relay = CdpRelay()
    session = relay.create_session("device-1", "run-1")
    companion, runner = FakeWebSocket(), FakeWebSocket()
    companion_task = asyncio.create_task(relay.attach_companion(session.id, "device-1", companion))
    runner_task = asyncio.create_task(relay.attach_runner(session.id, session.runner_secret, runner))
    await companion.incoming.put('{"id":1,"result":{}}')
    await runner.incoming.put('{"id":2,"method":"Page.navigate"}')
    assert await asyncio.wait_for(runner.sent.get(), 1) == '{"id":1,"result":{}}'
    assert await asyncio.wait_for(companion.sent.get(), 1) == '{"id":2,"method":"Page.navigate"}'
    await relay.close(session.id)
    await asyncio.gather(companion_task, runner_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_relay_rejects_wrong_device_duplicate_runner_and_unapproved_payload():
    relay = CdpRelay()
    session = relay.create_session("device-1", "run-1")
    with pytest.raises(RelayError):
        await relay.attach_companion(session.id, "device-2", FakeWebSocket())
    with pytest.raises(RelayError):
        await relay.attach_runner(session.id, "bad-secret", FakeWebSocket())
    with pytest.raises(RelayError):
        relay.create_session("device-1", "run-2")
    assert set(relay.control_message(session.id)) == {"type", "session_id", "run_id"}
    assert "script" not in str(relay.control_message(session.id))
    assert "password" not in str(relay.control_message(session.id))
    await relay.close(session.id)


@pytest.mark.asyncio
async def test_companion_disconnect_closes_runner_and_releases_device():
    relay = CdpRelay()
    session = relay.create_session("device-1", "run-1")
    companion, runner = FakeWebSocket(), FakeWebSocket()
    companion_task = asyncio.create_task(relay.attach_companion(session.id, "device-1", companion))
    runner_task = asyncio.create_task(relay.attach_runner(session.id, session.runner_secret, runner))
    await companion.incoming.put(None)
    await asyncio.gather(companion_task, runner_task, return_exceptions=True)
    assert runner.closed is True
    assert relay.create_session("device-1", "run-2").run_id == "run-2"
