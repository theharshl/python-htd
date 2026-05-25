import asyncio
import pytest
from unittest.mock import MagicMock
from htd_client.lync_client import HtdLyncClient
from htd_client.constants import HtdDeviceKind


@pytest.fixture
def lync_client():
    loop = MagicMock()
    model_info = {
        "zones": 6, "sources": 12, "friendly_name": "Lync6",
        "name": "Lync6", "kind": HtdDeviceKind.lync, "identifier": b'Wangine_Lync6'
    }
    client = HtdLyncClient(loop, model_info)
    client._connection = MagicMock()
    client._socket_lock = asyncio.Lock()
    client._zone_names = {}
    client._zone_data = {}
    client._source_names = {}
    return client


def test_get_zone_name_returns_none_before_query(lync_client):
    assert lync_client.get_zone_name(1) is None


def test_get_zone_name_returns_none_for_unknown_zone(lync_client):
    lync_client._zone_names[1] = "Living Room"
    assert lync_client.get_zone_name(99) is None


def test_get_zone_name_returns_cached_name(lync_client):
    lync_client._zone_names[1] = "Living Room"
    assert lync_client.get_zone_name(1) == "Living Room"


def test_zone_name_cached_independently_of_zone_data(lync_client):
    # Zone data does NOT exist for zone 2 yet
    # Simulate _handle_message processing a ZONE_NAME_RECEIVE_COMMAND for zone 2
    lync_client._zone_names[2] = "office"
    # zone_data should NOT be required for get_zone_name to work
    assert 2 not in lync_client._zone_data
    assert lync_client.get_zone_name(2) == "office"


def test_get_zone_name_reads_from_zone_names_dict(lync_client):
    lync_client._zone_names[1] = "living room"
    assert lync_client.get_zone_name(1) == "living room"
