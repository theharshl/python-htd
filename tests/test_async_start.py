"""Once deferred setup succeeds, Home Assistant stops retrying the config entry. The
library's backoff loop becomes the only thing that can bring the device back, so it must
start on a first failure, survive repeated failures, and stop cleanly on teardown."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from htd_client import build_client
from htd_client.constants import HtdConstants


def _client():
    return build_client(
        HtdConstants.SUPPORTED_MODELS["mca66"],
        network_address=("1.2.3.4", 10006),
    )


@pytest.mark.asyncio
async def test_async_start_does_not_raise_when_the_device_is_unreachable():
    """This is the entire fix for issue #30. If start raises, the integration falls back to
    ConfigEntryNotReady, no entities are created, and every HTD card stays Unavailable."""
    client = _client()

    with patch.object(client, "async_connect", new_callable=AsyncMock) as connect:
        connect.side_effect = OSError("no route to host")
        await client.async_start()

    assert client.connected is False
    client.disconnect()


@pytest.mark.asyncio
async def test_async_start_schedules_a_retry_after_a_failed_first_connect():
    """A client that has never connected previously had no retry loop at all — reconnect was
    only reachable from connection_lost. Without this the amplifier never comes back."""
    client = _client()

    with patch.object(client, "async_connect", new_callable=AsyncMock) as connect:
        connect.side_effect = OSError("no route to host")
        await client.async_start()

    assert client._reconnect_task is not None
    assert not client._reconnect_task.done()
    client.disconnect()


@pytest.mark.asyncio
async def test_async_start_does_not_schedule_a_retry_when_the_first_connect_works():
    """A healthy start must not leave a redundant loop dialing a device that is already up."""
    client = _client()

    with patch.object(client, "async_connect", new_callable=AsyncMock):
        await client.async_start()

    assert client._reconnect_task is None


@pytest.mark.asyncio
async def test_reconnect_backoff_doubles_to_a_sixty_second_ceiling():
    """An amplifier can be off for days. Retrying every second for days hammers the network
    and the log; an unbounded backoff would eventually never retry at all."""
    client = _client()
    # _disconnected defaults to True until async_connect/async_start runs; calling
    # _async_reconnect() directly (bypassing async_start) needs the same reset that
    # test_reconnect_logic in test_base_client_coverage.py already relies on.
    client._disconnected = False
    delays = []

    async def fake_sleep(delay):
        delays.append(delay)
        if len(delays) >= 8:
            client._disconnected = True

    with patch("htd_client.base_client.asyncio.sleep", new=fake_sleep), patch.object(
        client, "async_connect", new_callable=AsyncMock
    ) as connect:
        connect.side_effect = OSError("still off")
        await client._async_reconnect()

    assert delays[:4] == [1.0, 2.0, 4.0, 8.0]
    assert delays[-1] == 60.0


@pytest.mark.asyncio
async def test_reconnect_loop_exits_on_a_successful_connect():
    """The loop must stop dialing once it is back, or a reconnected client keeps opening
    connections underneath itself. On serial, every open can DTR-reset the gateway."""
    client = _client()
    # See note above: _async_reconnect() is being called directly, so _disconnected
    # needs the same manual reset async_start would otherwise perform.
    client._disconnected = False
    attempts = []

    async def fake_sleep(delay):
        attempts.append(delay)

    async def connect_third_time():
        if len(attempts) < 3:
            raise OSError("still off")
        client._connected = True

    with patch("htd_client.base_client.asyncio.sleep", new=fake_sleep), patch.object(
        client, "async_connect", side_effect=connect_third_time
    ):
        await client._async_reconnect()

    assert len(attempts) == 3


@pytest.mark.asyncio
async def test_reconnect_delay_resets_after_a_successful_connect():
    """Without a reset, a device that flaps once inherits a 60s recovery time for the rest of
    the process lifetime."""
    client = _client()
    client._reconnect_delay = 32.0

    client.connection_made(AsyncMock())
    await asyncio.sleep(0)

    assert client._reconnect_delay == 1.0
    if client._heartbeat_task is not None:
        client._heartbeat_task.cancel()


def test_disconnect_is_safe_on_a_client_that_never_connected():
    """Unload runs even when the device was never reachable. An AttributeError here leaves
    the config entry half-torn-down and the retry task orphaned."""
    client = build_client(
        HtdConstants.SUPPORTED_MODELS["mca66"],
        network_address=("1.2.3.4", 10006),
        loop=asyncio.new_event_loop(),
    )

    client.disconnect()

    assert client._disconnected is True


@pytest.mark.asyncio
async def test_disconnect_cancels_an_inflight_retry_task():
    """A retry loop that outlives the config entry keeps dialing hardware Home Assistant no
    longer manages, forever."""
    client = _client()

    with patch.object(client, "async_connect", new_callable=AsyncMock) as connect:
        connect.side_effect = OSError("no route to host")
        await client.async_start()

    task = client._reconnect_task
    client.disconnect()
    await asyncio.sleep(0)

    assert task.cancelled() or task.done()
