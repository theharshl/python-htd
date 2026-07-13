"""
.. code-block:: python

    # import the client
    from htd_client import HtdClient

    # Call its only function
    client = HtdClient("192.168.1.2")

    model_info = client.get_model_info()
    zone_info = client.query_zone(1)
    updated_zone_info = client.volume_up(1)
"""
import asyncio
import logging
from typing import Tuple

import htd_client.utils
from .base_client import BaseClient
from .constants import HtdCommonCommands, HtdModelInfo, HtdDeviceKind, HtdConstants
from .exceptions import HtdConnectionError
from .lync_client import HtdLyncClient
from .mca_client import HtdMcaClient

_LOGGER = logging.getLogger(__name__)


async def async_get_client(
    serial_address: str = None,
    network_address: Tuple[str, int] = None,
    loop: asyncio.AbstractEventLoop = None,
    retry_attempts: int = HtdConstants.DEFAULT_RETRY_ATTEMPTS,
) -> BaseClient:
    """
    Create a new client object.

    Args:
        network_address (str): The address to communicate with over TCP.
        serial_address (str): The location of the serial port.
        loop (asyncio.AbstractEventLoop): The event loop to use.
        retry_attempts (int): Number of times to retry a command before failing.

    Returns:
        HtdClient: The new client object.
    """

    address = f"serial: {serial_address}" if serial_address is not None else f"network: {network_address}"

    try:
        model_info = await async_get_model_info(
            loop if loop is not None else asyncio.get_running_loop(),
            network_address=network_address,
            serial_address=serial_address,
            retry_attempts=retry_attempts,
        )
    except OSError as e:
        raise HtdConnectionError(f"Unable to connect to HTD device ({address}): {e}") from e

    if model_info is None:
        raise HtdConnectionError(
            f"Unable to detect HTD device model ({address}). "
            f"Verify the device is powered on and the path/address is correct."
        )

    if model_info["kind"] == HtdDeviceKind.mca:
        client = HtdMcaClient(
            loop if loop is not None else asyncio.get_running_loop(),
            model_info,
            network_address=network_address,
            serial_address=serial_address,
            retry_attempts=retry_attempts,
        )

    elif model_info["kind"] == HtdDeviceKind.lync:
        client = HtdLyncClient(
            loop if loop is not None else asyncio.get_running_loop(),
            model_info,
            network_address=network_address,
            serial_address=serial_address,
            retry_attempts=retry_attempts,
        )

    else:
        raise ValueError(f"Unknown Device Kind: {model_info['kind']}")

    try:
        await client.async_connect()
    except OSError as e:
        raise HtdConnectionError(f"Unable to connect to HTD device ({address}): {e}") from e

    return client


async def async_get_model_info(
    loop: asyncio.AbstractEventLoop = None,
    network_address: Tuple[str, int] = None,
    serial_address:str=None,
    retry_attempts: int = HtdConstants.DEFAULT_RETRY_ATTEMPTS,
) -> HtdModelInfo | None:
    """
    Get the model information from the gateway.

    Returns:
         (str, str): the raw model name from the gateway and the friendly
         name, in a Tuple.
    """

    cmd = htd_client.utils.build_command(
        1, HtdCommonCommands.MODEL_QUERY_COMMAND_CODE, 0
    )

    def find_model(data: bytes) -> HtdModelInfo | None:
        for model_name in HtdConstants.SUPPORTED_MODELS:
            model = HtdConstants.SUPPORTED_MODELS[model_name]
            if model["identifier"] in data:
                return model
        return None

    # open the connection once and retry on it: every serial port open can
    # toggle DTR and reset the gateway, so re-opening per attempt would keep
    # resetting the device we are trying to probe
    reader, writer = await htd_client.utils.async_open_connection(
        loop if loop is not None else asyncio.get_running_loop(),
        network_address=network_address,
        serial_address=serial_address,
        settle_delay=HtdConstants.SERIAL_SETTLE_DELAY if serial_address is not None else 0,
    )

    try:
        for attempt in range(retry_attempts):
            writer.write(cmd)
            await writer.drain()

            data = await htd_client.utils.async_read_response(
                reader,
                response_complete=lambda d: find_model(d) is not None,
                timeout=HtdConstants.RESPONSE_TIMEOUT,
                quiet_window=HtdConstants.RESPONSE_QUIET_WINDOW,
            )

            model = find_model(data)
            if model is not None:
                return model

            if attempt < retry_attempts - 1:
                _LOGGER.warning(
                    "Model probe attempt %d/%d failed to match a known device, retrying",
                    attempt + 1,
                    retry_attempts,
                )
                await asyncio.sleep(HtdConstants.DEFAULT_COMMAND_RETRY_TIMEOUT)
    finally:
        writer.close()
        await writer.wait_closed()

    return None
