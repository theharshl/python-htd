"""build_client is what makes offline setup possible: it must decide zone and source counts
from a stored model definition alone, without opening a connection."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from htd_client import build_client, HtdLyncClient, HtdMcaClient
from htd_client.constants import HtdConstants


@pytest.mark.asyncio
async def test_build_client_selects_the_mca_class():
    """The class carries the protocol dialect. Building the wrong one sends Lync frames to
    an MCA66 and every command is silently ignored."""
    client = build_client(
        HtdConstants.SUPPORTED_MODELS["mca66"],
        network_address=("1.2.3.4", 10006),
    )
    assert isinstance(client, HtdMcaClient)
    assert client.get_zone_count() == 6


@pytest.mark.asyncio
async def test_build_client_selects_the_lync_class():
    """Lync 12 must yield 12 zones and 19 sources with the amplifier unplugged, or the
    offline restart creates the wrong number of entities."""
    client = build_client(
        HtdConstants.SUPPORTED_MODELS["lync12"],
        network_address=("1.2.3.4", 10006),
    )
    assert isinstance(client, HtdLyncClient)
    assert client.get_zone_count() == 12
    assert client.get_source_count() == 19


@pytest.mark.asyncio
async def test_build_client_opens_no_connection():
    """This is the whole contract. If build_client touched the transport, the offline setup
    path could not exist — it would fail for exactly the users it is meant to serve."""
    with patch(
        "htd_client.utils.async_open_connection", new_callable=AsyncMock
    ) as mock_open:
        client = build_client(
            HtdConstants.SUPPORTED_MODELS["mca66"],
            serial_address="/dev/ttyUSB0",
        )

    mock_open.assert_not_called()
    assert client.connected is False
    assert client.ready is False


@pytest.mark.asyncio
async def test_build_client_rejects_an_unknown_kind():
    """A malformed model definition must fail at the factory rather than producing a client
    that looks usable and does nothing."""
    bad_model = {**HtdConstants.SUPPORTED_MODELS["mca66"], "kind": "not-a-kind"}

    with pytest.raises(ValueError):
        build_client(bad_model, network_address=("1.2.3.4", 10006))


@pytest.mark.asyncio
async def test_async_get_client_still_probes_then_connects():
    """Guards the refactor. First-time setup and every legacy config entry still go through
    this path, and its behavior must not shift."""
    mock_client = MagicMock()
    mock_client.async_connect = AsyncMock()

    with patch(
        "htd_client.async_get_model_info", new_callable=AsyncMock
    ) as mock_probe, patch(
        "htd_client.build_client", return_value=mock_client
    ) as mock_build:
        mock_probe.return_value = HtdConstants.SUPPORTED_MODELS["mca66"]

        from htd_client import async_get_client

        result = await async_get_client(network_address=("1.2.3.4", 10006))

    assert result is mock_client
    mock_probe.assert_awaited_once()
    mock_build.assert_called_once()
    mock_client.async_connect.assert_awaited_once()
