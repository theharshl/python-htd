import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from htd_client import async_get_client, async_get_model_info, HtdMcaClient, HtdLyncClient
from htd_client.constants import HtdConstants, HtdDeviceKind

def _mock_connection():
    mock_reader = AsyncMock()
    mock_writer = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.wait_closed = AsyncMock()
    return mock_reader, mock_writer

@pytest.mark.asyncio
async def test_async_get_model_info_success():
    mock_loop = MagicMock()
    mock_reader, mock_writer = _mock_connection()

    with patch("htd_client.utils.async_open_connection", new_callable=AsyncMock) as mock_open, \
         patch("htd_client.utils.async_read_response", new_callable=AsyncMock) as mock_read:
        mock_open.return_value = (mock_reader, mock_writer)
        mock_read.return_value = b"Wangine_MCA66"

        model = await async_get_model_info(loop=mock_loop, network_address=("1.2.3.4", 10006))

        assert model == HtdConstants.SUPPORTED_MODELS["mca66"]
        mock_read.assert_called_once()
        mock_writer.close.assert_called_once()

@pytest.mark.asyncio
async def test_async_get_model_info_failure():
    mock_loop = MagicMock()
    mock_reader, mock_writer = _mock_connection()

    with patch("htd_client.utils.async_open_connection", new_callable=AsyncMock) as mock_open, \
         patch("htd_client.utils.async_read_response", new_callable=AsyncMock) as mock_read, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        mock_open.return_value = (mock_reader, mock_writer)
        mock_read.return_value = b"Unknown Device"

        model = await async_get_model_info(loop=mock_loop, network_address=("1.2.3.4", 10006), retry_attempts=2)

        assert model is None
        assert mock_read.call_count == 2
        assert mock_open.call_count == 1
        mock_writer.close.assert_called_once()

@pytest.mark.asyncio
async def test_async_get_model_info_retries_then_succeeds():
    mock_loop = MagicMock()
    mock_reader, mock_writer = _mock_connection()

    with patch("htd_client.utils.async_open_connection", new_callable=AsyncMock) as mock_open, \
         patch("htd_client.utils.async_read_response", new_callable=AsyncMock) as mock_read, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_open.return_value = (mock_reader, mock_writer)
        mock_read.side_effect = [b"Unknown Device", b"Wangine_MCA66"]

        model = await async_get_model_info(loop=mock_loop, network_address=("1.2.3.4", 10006), retry_attempts=3)

        assert model == HtdConstants.SUPPORTED_MODELS["mca66"]
        assert mock_read.call_count == 2
        mock_sleep.assert_called_once_with(HtdConstants.DEFAULT_COMMAND_RETRY_TIMEOUT)

@pytest.mark.asyncio
async def test_async_get_model_info_passes_settle_delay_for_serial():
    mock_loop = MagicMock()
    mock_reader, mock_writer = _mock_connection()

    with patch("htd_client.utils.async_open_connection", new_callable=AsyncMock) as mock_open, \
         patch("htd_client.utils.async_read_response", new_callable=AsyncMock) as mock_read:
        mock_open.return_value = (mock_reader, mock_writer)
        mock_read.return_value = b"Wangine_MCA66"

        await async_get_model_info(loop=mock_loop, serial_address="/dev/ttyUSB0")

        _, kwargs = mock_open.call_args
        assert kwargs["settle_delay"] == HtdConstants.SERIAL_SETTLE_DELAY

@pytest.mark.asyncio
async def test_async_get_client_mca():
    mock_loop = MagicMock()
    
    with patch("htd_client.async_get_model_info", new_callable=AsyncMock) as mock_get_info:
        model_info = HtdConstants.SUPPORTED_MODELS["mca66"]
        mock_get_info.return_value = model_info
        
        with patch("htd_client.mca_client.HtdMcaClient.async_connect", new_callable=AsyncMock) as mock_connect:
            client = await async_get_client(loop=mock_loop, network_address=("1.2.3.4", 10006))
            
            assert isinstance(client, HtdMcaClient)
            mock_connect.assert_called_once()

@pytest.mark.asyncio
async def test_async_get_client_lync():
    mock_loop = MagicMock()
    
    with patch("htd_client.async_get_model_info", new_callable=AsyncMock) as mock_get_info:
        model_info = HtdConstants.SUPPORTED_MODELS["lync6"]
        mock_get_info.return_value = model_info
        
        with patch("htd_client.lync_client.HtdLyncClient.async_connect", new_callable=AsyncMock) as mock_connect:
            client = await async_get_client(loop=mock_loop, network_address=("1.2.3.4", 10006))
            
            assert isinstance(client, HtdLyncClient)
            mock_connect.assert_called_once()

@pytest.mark.asyncio
async def test_async_get_client_unknown():
    mock_loop = MagicMock()

    with patch("htd_client.async_get_model_info", new_callable=AsyncMock) as mock_get_info:
        mock_get_info.return_value = {"kind": "unknown_kind"}

        with pytest.raises(ValueError, match="Unknown Device Kind"):
            await async_get_client(loop=mock_loop, network_address=("1.2.3.4", 10006))

@pytest.mark.asyncio
async def test_async_get_client_raises_clear_error_when_model_undetected():
    mock_loop = MagicMock()

    with patch("htd_client.async_get_model_info", new_callable=AsyncMock) as mock_get_info:
        mock_get_info.return_value = None

        with pytest.raises(ValueError, match="Unable to detect HTD device model"):
            await async_get_client(loop=mock_loop, serial_address="/dev/serial/by-id/usb-example")
