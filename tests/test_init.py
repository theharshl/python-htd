import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from htd_client import async_get_client, async_get_model_info, HtdMcaClient, HtdLyncClient
from htd_client.constants import HtdConstants, HtdDeviceKind

@pytest.mark.asyncio
async def test_async_get_model_info_success():
    mock_loop = MagicMock()
    mock_response = b"MCA-66" 
    
    # MCA-66 identifier is "MCA-66" in constants? Let's check constants.py content implicitly or mock it.
    # Actually, let's look at what async_get_model_info does.
    # It sends MODEL_QUERY_COMMAND_CODE.
    # It iterates HtdConstants.SUPPORTED_MODELS and checks if model["identifier"] is in response.
    
    with patch("htd_client.utils.async_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = b"Wangine_MCA66"
        
        model = await async_get_model_info(loop=mock_loop, network_address=("1.2.3.4", 10006))
        
        assert model == HtdConstants.SUPPORTED_MODELS["mca66"]
        mock_send.assert_called_once()

@pytest.mark.asyncio
async def test_async_get_model_info_failure():
    mock_loop = MagicMock()

    with patch("htd_client.utils.async_send_command", new_callable=AsyncMock) as mock_send, \
         patch("asyncio.sleep", new_callable=AsyncMock):
        mock_send.return_value = b"Unknown Device"

        model = await async_get_model_info(loop=mock_loop, network_address=("1.2.3.4", 10006), retry_attempts=2)

        assert model is None
        assert mock_send.call_count == 2

@pytest.mark.asyncio
async def test_async_get_model_info_retries_then_succeeds():
    mock_loop = MagicMock()

    with patch("htd_client.utils.async_send_command", new_callable=AsyncMock) as mock_send, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_send.side_effect = [b"Unknown Device", b"Wangine_MCA66"]

        model = await async_get_model_info(loop=mock_loop, network_address=("1.2.3.4", 10006), retry_attempts=3)

        assert model == HtdConstants.SUPPORTED_MODELS["mca66"]
        assert mock_send.call_count == 2
        mock_sleep.assert_called_once_with(HtdConstants.DEFAULT_COMMAND_RETRY_TIMEOUT)

@pytest.mark.asyncio
async def test_async_get_model_info_passes_settle_delay_for_serial():
    mock_loop = MagicMock()

    with patch("htd_client.utils.async_send_command", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = b"Wangine_MCA66"

        await async_get_model_info(loop=mock_loop, serial_address="/dev/ttyUSB0")

        _, kwargs = mock_send.call_args
        assert kwargs["settle_delay"] == HtdConstants.MODEL_PROBE_SETTLE_DELAY

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
