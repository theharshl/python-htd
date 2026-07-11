import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from htd_client.constants import HtdConstants, HtdDeviceKind
from htd_client.utils import (
    convert_value,
    stringify_bytes_raw,
    stringify_bytes,
    convert_volume_to_raw,
    decode_response,
    parse_zone_name,
    async_open_connection,
    async_read_response
)

def test_convert_value():
    assert convert_value(0x10) == 0x10
    # convert_value returns value - 0x100 if value > 0x7F
    assert convert_value(0x80) == -128 
    assert convert_value(0xFF) == -1

def test_stringify_bytes_raw():
    b = bytes([0x01, 0x02, 0xFF])
    assert stringify_bytes_raw(b, "hex") == "0x01 0x02 0xff"
    
    with pytest.raises(ValueError):
        stringify_bytes_raw(b, "unknown")

def test_stringify_bytes():
    # Chunk size is 14.
    data = bytes(range(14))
    output = stringify_bytes(data)
    assert "[ 1]" in output

def test_convert_volume_to_raw():
    # MAX_RAW_VOLUME = 256, MAX_VOLUME = 60
    assert convert_volume_to_raw(60) == 0
    # MAX_RAW_VOLUME - (MAX_VOLUME - volume)
    # 0 -> 256 - (60 - 0) = 196
    assert convert_volume_to_raw(0) == 196
    # 30 -> 256 - (60 - 30) = 226
    assert convert_volume_to_raw(30) == 226

def test_decode_response():
    assert decode_response(b"hello") == "hello"

def test_parse_zone_name():
    # NAME_START_INDEX = 4. LENGTH = 10.
    # 0,1,2,3, NAME...
    prefix = b"\x00\x00\x00\x00"
    name = b"Zone1"
    padding = b"\x00" * (10 - len(name))
    data = prefix + name + padding + b"EXTRA"
    
    assert parse_zone_name(data) == "Zone1"

@pytest.mark.asyncio
async def test_async_open_connection_network():
    mock_loop = MagicMock()
    mock_reader = AsyncMock()
    mock_writer = MagicMock()

    with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_open:
        mock_open.return_value = (mock_reader, mock_writer)

        reader, writer = await async_open_connection(mock_loop, network_address=("1.2.3.4", 1234))

        mock_open.assert_called_with("1.2.3.4", 1234)
        assert reader is mock_reader
        assert writer is mock_writer

@pytest.mark.asyncio
async def test_async_open_connection_serial():
    mock_loop = MagicMock()
    mock_reader = AsyncMock()
    mock_writer = MagicMock()

    with patch("htd_client.utils.open_serial_connection", new_callable=AsyncMock) as mock_open:
        mock_open.return_value = (mock_reader, mock_writer)

        reader, writer = await async_open_connection(mock_loop, serial_address="/dev/ttyUSB0")

        mock_open.assert_called()
        assert reader is mock_reader
        assert writer is mock_writer

@pytest.mark.asyncio
async def test_async_open_connection_no_address():
    mock_loop = MagicMock()

    with pytest.raises(ValueError, match="unable to connect"):
        await async_open_connection(mock_loop)

@pytest.mark.asyncio
async def test_async_open_connection_serial_settle_delay():
    mock_loop = MagicMock()
    mock_reader = AsyncMock()
    mock_writer = MagicMock()

    with patch("htd_client.utils.open_serial_connection", new_callable=AsyncMock) as mock_open, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_open.return_value = (mock_reader, mock_writer)

        await async_open_connection(mock_loop, serial_address="/dev/ttyUSB0", settle_delay=1.5)

        mock_sleep.assert_called_once_with(1.5)

@pytest.mark.asyncio
async def test_async_open_connection_no_settle_delay_by_default():
    mock_loop = MagicMock()
    mock_reader = AsyncMock()
    mock_writer = MagicMock()

    with patch("htd_client.utils.open_serial_connection", new_callable=AsyncMock) as mock_open, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_open.return_value = (mock_reader, mock_writer)

        await async_open_connection(mock_loop, serial_address="/dev/ttyUSB0")

        mock_sleep.assert_not_called()

@pytest.mark.asyncio
async def test_async_read_response_returns_after_quiet_window():
    """Without a predicate, reading stops once the line goes quiet."""
    import asyncio as _asyncio

    mock_reader = MagicMock()
    chunks = [b"response"]

    async def read(n):
        if chunks:
            return chunks.pop(0)
        await _asyncio.get_running_loop().create_future()

    mock_reader.read = read

    response = await async_read_response(mock_reader, timeout=0.5, quiet_window=0.02)

    assert response == b"response"
