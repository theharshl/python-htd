"""Tests for robustness against slow / low-quality USB-serial adapters.

A cheap adapter can:
- deliver a reply split across multiple small reads (partial read)
- delay the reply while the gateway reboots after a DTR toggle on port open
- never deliver a reply at all (command lost during gateway reset)
- deliver line noise before the real reply

The model probe must tolerate all of these, must not re-open the port
between retries (each open DTR-resets the gateway), and the persistent
connection must let the gateway settle before the first write.
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from htd_client import async_get_model_info
from htd_client.constants import HtdConstants

from tests.test_base_client_additional import ConcreteClient

MCA66_REPLY = b"Wangine_MCA66"


def make_writer():
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    return writer


def fast_timing():
    """Shrink real-time waits so tests stay fast."""
    return (
        patch.object(HtdConstants, "SERIAL_SETTLE_DELAY", 0),
        patch.object(HtdConstants, "RESPONSE_TIMEOUT", 0.2),
        patch.object(HtdConstants, "RESPONSE_QUIET_WINDOW", 0.05),
        patch.object(HtdConstants, "DEFAULT_COMMAND_RETRY_TIMEOUT", 0.01),
    )


def apply_patches(patches):
    for p in patches:
        p.start()


def stop_patches(patches):
    for p in patches:
        p.stop()


@pytest.fixture
def timing():
    patches = fast_timing()
    apply_patches(patches)
    yield
    stop_patches(patches)


@pytest.mark.asyncio
async def test_model_detected_when_reply_arrives_in_chunks(timing):
    """A reply split across USB packets must still match the identifier."""
    mock_reader = AsyncMock()
    mock_reader.read.side_effect = [b"Wangine_", b"MCA66", b""]
    mock_writer = make_writer()

    with patch(
        "htd_client.utils.open_serial_connection", new_callable=AsyncMock
    ) as mock_open:
        mock_open.return_value = (mock_reader, mock_writer)

        model = await async_get_model_info(serial_address="/dev/ttyUSB0")

    assert model == HtdConstants.SUPPORTED_MODELS["mca66"]
    assert mock_open.call_count == 1


@pytest.mark.asyncio
async def test_probe_returns_none_instead_of_hanging_when_no_reply(timing):
    """If the gateway never answers (command lost during its DTR reset),
    the probe must give up within its deadline, not await forever."""

    async def hang(*args, **kwargs):
        await asyncio.get_running_loop().create_future()

    mock_reader = MagicMock()
    mock_reader.read = hang
    mock_writer = make_writer()

    with patch(
        "htd_client.utils.open_serial_connection", new_callable=AsyncMock
    ) as mock_open:
        mock_open.return_value = (mock_reader, mock_writer)

        model = await asyncio.wait_for(
            async_get_model_info(serial_address="/dev/ttyUSB0", retry_attempts=2),
            timeout=5,
        )

    assert model is None


@pytest.mark.asyncio
async def test_probe_opens_serial_port_once_across_retries(timing):
    """Each port open DTR-resets the gateway, so probe retries must reuse
    the already-open port instead of re-opening it per attempt."""
    mock_reader = AsyncMock()
    # each attempt reads garbage then EOF; three attempts' worth
    mock_reader.read.side_effect = [b"garbage", b"", b"junk", b"", b"noise", b""]
    mock_writer = make_writer()

    with patch(
        "htd_client.utils.open_serial_connection", new_callable=AsyncMock
    ) as mock_open:
        mock_open.return_value = (mock_reader, mock_writer)

        model = await async_get_model_info(
            serial_address="/dev/ttyUSB0", retry_attempts=3
        )

    assert model is None
    assert mock_open.call_count == 1
    # the command was actually retried on the one open connection
    assert mock_writer.write.call_count == 3


@pytest.mark.asyncio
async def test_model_detected_with_noise_before_reply(timing):
    """Line noise from the gateway reset (including bytes that look like a
    message header) must not prevent the identifier match."""
    noisy = b"\x00\xff" + HtdConstants.MESSAGE_HEADER + b"\xfa" + MCA66_REPLY
    mock_reader = AsyncMock()
    mock_reader.read.side_effect = [noisy, b""]
    mock_writer = make_writer()

    with patch(
        "htd_client.utils.open_serial_connection", new_callable=AsyncMock
    ) as mock_open:
        mock_open.return_value = (mock_reader, mock_writer)

        model = await async_get_model_info(serial_address="/dev/ttyUSB0")

    assert model == HtdConstants.SUPPORTED_MODELS["mca66"]


@pytest.mark.asyncio
async def test_probe_stops_reading_once_model_identified(timing):
    """Once the identifier is in the buffer the probe should return without
    waiting out the quiet window or issuing further reads."""
    mock_reader = AsyncMock()
    mock_reader.read.side_effect = [
        MCA66_REPLY,
        RuntimeError("probe kept reading after the reply already matched"),
    ]
    mock_writer = make_writer()

    with patch(
        "htd_client.utils.open_serial_connection", new_callable=AsyncMock
    ) as mock_open:
        mock_open.return_value = (mock_reader, mock_writer)

        model = await async_get_model_info(serial_address="/dev/ttyUSB0")

    assert model == HtdConstants.SUPPORTED_MODELS["mca66"]


@pytest.mark.asyncio
async def test_serial_settle_delay_applied_once_before_first_write(timing):
    """The settle delay is paid once, after the single port open, before the
    first probe write — not once per retry."""
    stop_patches_needed = patch.object(HtdConstants, "SERIAL_SETTLE_DELAY", 1.5)
    stop_patches_needed.start()
    try:
        mock_reader = AsyncMock()
        mock_reader.read.side_effect = [b"garbage", b"", b"junk", b"", b"noise", b""]
        mock_writer = make_writer()

        with patch(
            "htd_client.utils.open_serial_connection", new_callable=AsyncMock
        ) as mock_open, patch(
            "asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            mock_open.return_value = (mock_reader, mock_writer)

            await async_get_model_info(serial_address="/dev/ttyUSB0", retry_attempts=3)

        settle_calls = [
            c for c in mock_sleep.call_args_list if c.args and c.args[0] == 1.5
        ]
        assert len(settle_calls) == 1
    finally:
        stop_patches_needed.stop()


@pytest.mark.asyncio
async def test_heartbeat_settles_before_first_refresh_on_serial():
    """The persistent connection's port open also DTR-resets the gateway;
    the first refresh write must wait for the settle delay or it is lost."""
    loop = MagicMock()
    model_info = HtdConstants.SUPPORTED_MODELS["mca66"]
    client = ConcreteClient(loop, model_info, serial_address="/dev/ttyUSB0")
    client._connected = True

    events = []

    async def fake_refresh(zone=None):
        events.append("refresh")
        client._connected = False

    async def fake_sleep(delay):
        events.append(("sleep", delay))

    client.refresh = fake_refresh

    with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=fake_sleep):
        await client._heartbeat()

    assert events[0] == ("sleep", HtdConstants.SERIAL_SETTLE_DELAY)
    assert "refresh" in events


@pytest.mark.asyncio
async def test_heartbeat_does_not_delay_first_refresh_on_network():
    """Network connections have no DTR reset; refresh should fire immediately."""
    loop = MagicMock()
    model_info = HtdConstants.SUPPORTED_MODELS["mca66"]
    client = ConcreteClient(loop, model_info, network_address=("1.2.3.4", 10006))
    client._connected = True

    events = []

    async def fake_refresh(zone=None):
        events.append("refresh")
        client._connected = False

    async def fake_sleep(delay):
        events.append(("sleep", delay))

    client.refresh = fake_refresh

    with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=fake_sleep):
        await client._heartbeat()

    assert events[0] == "refresh"
