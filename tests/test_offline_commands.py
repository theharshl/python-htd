"""Commands issued while the amplifier is off must fail with the library's own exception type.
The integration translates exactly one type into a visible Home Assistant error; an
AttributeError from a None transport surfaces as an opaque failure with no useful trace."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from htd_client import build_client
from htd_client.constants import HtdConstants
from htd_client.exceptions import HtdConnectionError


def _mca():
    return build_client(
        HtdConstants.SUPPORTED_MODELS["mca66"],
        network_address=("1.2.3.4", 10006),
    )


def _lync():
    return build_client(
        HtdConstants.SUPPORTED_MODELS["lync12"],
        network_address=("1.2.3.4", 10006),
    )


@pytest.mark.asyncio
async def test_send_cmd_raises_a_connection_error_when_never_connected():
    """`self._connection.write(cmd)` on a None transport raises AttributeError, which the
    integration cannot distinguish from a genuine bug in its own code."""
    client = _mca()

    with pytest.raises(HtdConnectionError):
        await client._send_cmd(1, 0x04, 0x00)


@pytest.mark.asyncio
async def test_send_cmd_raises_a_connection_error_after_the_link_drops():
    """A transport can still be set after connection_lost; `connected` is the real signal."""
    client = _mca()
    client._connection = MagicMock()
    client._connected = False

    with pytest.raises(HtdConnectionError):
        await client._send_cmd(1, 0x04, 0x00)


@pytest.mark.asyncio
async def test_mca_refresh_raises_a_connection_error_when_disconnected():
    """Entities call refresh() as they are added. Offline that must be a catchable no-op,
    not a traceback during every startup."""
    client = _mca()

    with pytest.raises(HtdConnectionError):
        await client.refresh()


@pytest.mark.asyncio
async def test_lync_refresh_raises_a_connection_error_when_disconnected():
    """Same contract on the other protocol dialect."""
    client = _lync()

    with pytest.raises(HtdConnectionError):
        await client.refresh()


@pytest.mark.asyncio
async def test_heartbeat_stops_quietly_when_the_connection_drops():
    """The 60s heartbeat runs for the life of the process. If a disconnected refresh escapes
    it, an outage produces 'Task exception was never retrieved' spam until the amp returns."""
    client = _mca()
    client._connected = True
    client._connection = None

    await client._heartbeat()

    assert client._connected is True


@pytest.mark.asyncio
async def test_connection_lost_broadcasts_so_entities_can_repaint():
    """Every platform sets should_poll = False, so a card only ever repaints on a broadcast.
    Without this, a dropped connection leaves stale live values on screen indefinitely."""
    client = _mca()
    seen = []
    await client.async_subscribe(lambda zone: seen.append(zone))

    client.connection_lost(None)
    await asyncio.sleep(0.01)

    assert seen == [None]


@pytest.mark.asyncio
async def test_connection_made_broadcasts_so_entities_can_come_back():
    """The transition out of an outage is the moment restored assumed-state values must be
    replaced by live ones."""
    client = _mca()
    seen = []
    await client.async_subscribe(lambda zone: seen.append(zone))

    client.connection_made(MagicMock())
    await asyncio.sleep(0.01)

    assert seen == [None]

    if client._heartbeat_task is not None:
        client._heartbeat_task.cancel()
