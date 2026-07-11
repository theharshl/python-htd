import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from htd_client.base_client import BaseClient
from htd_client.constants import HtdConstants, HtdCommonCommands, HtdDeviceKind

class ConcreteClient(BaseClient):
    async def refresh(self, zone: int = None): pass
    async def power_on_all_zones(self): pass
    async def power_off_all_zones(self): pass
    async def async_set_source(self, zone: int, source: int): pass
    async def async_volume_up(self, zone: int): pass
    async def async_set_volume(self, zone: int, volume: int): pass
    async def async_volume_down(self, zone: int): pass
    async def async_mute(self, zone: int): pass
    async def async_unmute(self, zone: int): pass
    async def async_power_on(self, zone: int): pass
    async def async_power_off(self, zone: int): pass
    async def async_bass_up(self, zone: int): pass
    async def async_bass_down(self, zone: int): pass
    async def async_treble_up(self, zone: int): pass
    async def async_treble_down(self, zone: int): pass
    async def async_balance_left(self, zone: int): pass
    async def async_balance_right(self, zone: int): pass

@pytest.fixture
def client():
    mock_model_info = {
        "zones": 6,
        "sources": 6,
        "friendly_name": "MCA66",
        "name": "MCA66",
        "kind": HtdDeviceKind.mca,
        "identifier": b'Wangine_MCA66'
    }
    loop = MagicMock()
    # Mock create_task to return a mock task
    mock_task = MagicMock()
    mock_task.cancel = MagicMock()
    loop.create_task.return_value = mock_task
    
    c = ConcreteClient(loop, mock_model_info, network_address=("1.2.3.4", 10006))
    c._connection = MagicMock()
    c._subscribers = set()
    c._zone_data = {}
    c._zone_names = {}
    return c

def test_process_next_command_invalid_header(client):
    # Data len must be >= 6 (HEADER + 4)
    # Header at index 4.
    data = b"junk" + bytes([HtdConstants.HEADER_BYTE, HtdConstants.RESERVED_BYTE]) + bytes([1, 2, 3, 4])
    # Total len: 4 + 2 + 4 = 10. >= 6.
    
    # Process junk only (len 4). Returns 0.
    zone_ret, consumed = client._process_next_command(b"junk")
    assert consumed == 0
    
    # Process data with header at 4.
    zone_ret, consumed = client._process_next_command(data)
    # Header found at 4.
    # Command check needs data.
    # Returns 0 if not enough data?
    # Start=4. Zone=6. Cmd=7. Data=8.
    # Len 10.
    # Cmd is data[7]=2. Invalid cmd.
    # Returns start + HEADER = 6.
    assert consumed == 6

def test_process_next_command_unknown_command(client):
    header = bytes([HtdConstants.HEADER_BYTE, HtdConstants.RESERVED_BYTE])
    # Command 0xFF is likely unknown
    cmd = 0xFF
    # Need len >= 6.
    # Header(2) + Zone(1) + Cmd(1) + Data(2).
    frame = header + bytes([1, cmd, 0, 0]) 
    
    zone_ret, consumed = client._process_next_command(frame)
    assert zone_ret is None
    assert consumed == 2

def test_process_next_command_checksum_fail(client):
    header = bytes([HtdConstants.HEADER_BYTE, HtdConstants.RESERVED_BYTE])
    zone = 1
    cmd = HtdCommonCommands.ZONE_STATUS_RECEIVE_COMMAND
    # Expected len 9.
    data = bytes([0]*9)
    checksum = 0xFF # Invalid

    full = header + bytes([zone, cmd]) + data + bytes([checksum])

    # A checksum failure means the declared frame length can't be trusted
    # (it may be a coincidental match on garbage/misaligned bytes), so we
    # must NOT skip the whole presumed frame. Resync minimally by only the
    # header length, same as the unknown-command path, so the next byte
    # onward is re-scanned for a real header instead of staying corrupted.
    zone_ret, consumed = client._process_next_command(full)
    assert zone_ret is None
    assert consumed == HtdConstants.MESSAGE_HEADER_LENGTH

    # Check that _parse_command NOT called
    with patch.object(client, '_parse_command') as mock_parse:
        client._process_next_command(full)
        mock_parse.assert_not_called()

def test_process_next_command_checksum_fail_recovers_next_frame(client):
    """A single corrupted frame must not desync parsing of the frame after it."""
    header = bytes([HtdConstants.HEADER_BYTE, HtdConstants.RESERVED_BYTE])

    def build_zone_status(zone, checksum_override=None):
        cmd = HtdCommonCommands.ZONE_STATUS_RECEIVE_COMMAND
        data = bytes([0, 0, 0, 0, 1, 0xe2, 0, 0, 0])
        frame = header + bytes([zone, cmd]) + data
        checksum = checksum_override
        if checksum is None:
            checksum = sum(frame) & 0xFF
        return frame + bytes([checksum])

    bad_frame = build_zone_status(1, checksum_override=0xFF)
    good_frame = build_zone_status(2)
    buffer = bad_frame + good_frame

    with patch.object(client, '_parse_command') as mock_parse:
        zone_ret, consumed = client._process_next_command(buffer)
        assert zone_ret is None
        assert consumed == HtdConstants.MESSAGE_HEADER_LENGTH
        mock_parse.assert_not_called()

        # advance past the corrupted frame's header the same way data_received does
        remaining = buffer[consumed:]
        zone_ret, consumed = client._process_next_command(remaining)
        assert zone_ret == 2
        mock_parse.assert_called_once()

def test_parse_command_Zonename(client):
    zone = 1
    cmd = HtdCommonCommands.ZONE_NAME_RECEIVE_COMMAND
    name = b"Kitchen"
    # padded
    data = name + b" " * (11 - len(name)) # padded with nulls usually?
    # Code strips nulls.
    
    client._zone_data[1] = MagicMock()
    # Mock ZoneDetail
    client._zone_data[1].name = None
    
    client._parse_command(zone, cmd, data)
    # assert client._zone_data[1].name.lower() == "kitchen"
    # Actually name is decoded.
    # Let's check logic:
    # name = str(data[0:11].decode().rstrip('\0')).lower()
    pass

def test_on_data_exception(client):
    client._process_next_command = MagicMock(side_effect=Exception("Boom"))
    client.refresh = AsyncMock()
    client._loop.create_task = MagicMock()
    
    client.data_received(b"123")
    assert client._buffer is None
    client._loop.create_task.assert_called()
