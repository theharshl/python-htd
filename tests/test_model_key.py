"""The model key is the single thing that makes an offline restart possible: it is what a
consumer persists so it can rebuild the right client without asking the device who it is."""
import asyncio

import pytest

from htd_client import build_client, get_model_info
from htd_client.constants import HtdConstants


def test_every_supported_model_carries_its_own_lookup_key():
    """The key is what gets written to storage. If it does not match the dict key it was
    stored under, a round-trip through storage resolves to the wrong hardware — a Lync 12
    entry rebuilt as an MCA66 would silently create 6 entities instead of 12."""
    for name, model in HtdConstants.SUPPORTED_MODELS.items():
        assert model["key"] == name


def test_get_model_info_round_trips_a_persisted_key():
    """A consumer that stored "mca66" last run must get back the same zone and source counts
    with the amplifier powered off. These two numbers are what gate entity creation."""
    model = get_model_info("mca66")
    assert model is HtdConstants.SUPPORTED_MODELS["mca66"]
    assert model["zones"] == 6
    assert model["sources"] == 6


def test_get_model_info_returns_none_for_an_unknown_key():
    """An entry written by a newer version and then rolled back must degrade to a live probe,
    not raise. The caller branches on None to choose the probe path."""
    assert get_model_info("lync24") is None


def test_get_model_info_returns_none_for_a_missing_key():
    """Config entries created before this feature have no key at all. The caller passes the
    missing value straight through rather than special-casing it."""
    assert get_model_info(None) is None


@pytest.mark.asyncio
async def test_get_source_names_reports_only_what_the_controller_said():
    """Callers persist this dict across restarts. get_source_name() invents a "Source N"
    placeholder for anything unknown, so caching its output would freeze placeholders into
    storage forever and permanently destroy real controller names."""
    client = build_client(
        HtdConstants.SUPPORTED_MODELS["lync12"],
        network_address=("1.2.3.4", 10006),
    )
    client._source_names = {2: "turntable"}

    assert client.get_source_names() == {2: "turntable"}
    assert client.get_source_name(1) == "Source 1"


@pytest.mark.asyncio
async def test_get_zone_names_reports_only_what_the_controller_said():
    """Same contract as sources, and the one the name-cache regression guard depends on."""
    client = build_client(
        HtdConstants.SUPPORTED_MODELS["lync12"],
        network_address=("1.2.3.4", 10006),
    )
    client._zone_names = {3: "kitchen"}

    assert client.get_zone_names() == {3: "kitchen"}
