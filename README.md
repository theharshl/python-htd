# htd-client-ha

Python async client for Home Theater Direct (HTD) whole-home audio systems. Supports the MCA-66, Lync 6, and Lync 12 over TCP or serial.

This is a maintained fork of [hikirsch/python-htd](https://github.com/hikirsch/python-htd) with full Lync support, zone/source naming, DND, and EQ controls.

## Supported Hardware

| Model   | Zones | Sources | Kind   |
|---------|-------|---------|--------|
| MCA-66  | 6     | 6       | `mca`  |
| Lync 6  | 6     | 12      | `lync` |
| Lync 12 | 12    | 19      | `lync` |

The device model is auto-detected at connection time.

## Installation

```bash
pip install htd-client-ha
```

## Usage

```python
import asyncio
from htd_client import async_get_client

async def main():
    # Connect over TCP (most common — via the HTD network gateway)
    client = await async_get_client(network_address=("192.168.1.100", 10006))
    await client.async_connect()
    await client.async_wait_until_ready()

    # Query all zone state
    await client.refresh()

    # Control a zone
    await client.async_power_on(zone=1)
    await client.async_set_volume(zone=1, volume=20)
    await client.async_set_source(zone=1, source=1)

    # Subscribe to zone state changes (push model)
    async def on_zone_update(zone):
        print(f"Zone {zone} updated")
    await client.async_subscribe(on_zone_update)

asyncio.run(main())
```

```python
# Or connect over serial (RS-232, or USB-serial adapter)
client = await async_get_client(serial_address="/dev/ttyUSB0")
```

### Serial Connection Reliability

Serial connections — especially cheap USB-serial adapters — are hardened against the failure modes that used to trip them up:

- Opening the port no longer races the device's DTR-triggered reset; the client waits out a settle delay before writing.
- Replies delivered across multiple USB packets are now read to completion instead of being misread as a failed probe.
- A single corrupted or dropped byte resyncs cleanly instead of permanently desyncing the parser into a stream of errors.

### Zone and Source Names (Lync only)

```python
# Query names from the controller (results cached on client)
await client.async_query_zone_name(zone=1)
await client.async_query_source_name(source=1)

# Read cached names
zone_name = client.get_zone_name(zone=1)
source_name = client.get_source_name(source=1)

# Set names on the controller
await client.async_set_zone_name(zone=1, name="Living Room")
await client.async_set_source_name(source=1, name="Sonos")
```

### EQ Controls

```python
await client.async_set_bass(zone=1, bass=5)
await client.async_set_treble(zone=1, treble=-2)
await client.async_set_balance(zone=1, balance=0)
```

### Do Not Disturb (Lync only)

```python
# Exclude a zone from party mode / all-zone commands
await client.async_set_dnd(zone=1, dnd=True)
```

## API Reference

### `get_model_info(key: str | None) -> HtdModelInfo | None`

Look up a model definition by its persistable key (`"mca66"`, `"lync6"`, `"lync12"`) without
touching the device. Returns `None` for an unknown or missing key. Pair it with
`build_client` to bring a client up while the device is powered off:

```python
from htd_client import build_client, get_model_info

model_info = get_model_info(stored_key)      # None if never stored
if model_info is not None:
    client = build_client(model_info, network_address=("192.168.1.2", 10006))
    await client.async_start()               # connects in the background, never raises
```

Every entry in `HtdConstants.SUPPORTED_MODELS` carries its own key under `model_info["key"]`,
so a caller that probed once can record it and skip the probe on later runs.

### `build_client(model_info, *, serial_address=None, network_address=None, loop=None, retry_attempts=3) -> BaseClient`

Create a client of the class matching `model_info["kind"]`. Performs no I/O — nothing is
opened, probed or connected. Raises `ValueError` for an unrecognized kind. Call
`async_connect()` or `async_start()` afterwards.

### `BaseClient.async_start() -> None`

Connect if the device is reachable, and otherwise start a background retry loop
(1s, doubling to a 60s ceiling) and return. Unlike `async_connect()`, this never raises.
Intended for long-lived consumers that must come up whether or not the device is powered on.

`disconnect()` stops that loop and is safe to call on a client that never connected.

### `async_get_client(...) -> BaseClient`

Factory function that auto-detects the device model and returns the appropriate client.

| Parameter | Type | Description |
|-----------|------|-------------|
| `network_address` | `(str, int)` | `(host, port)` for TCP connection |
| `serial_address` | `str` | Serial port path for RS-232 connection |
| `retry_attempts` | `int` | Command retry count (default: 3) |

### `BaseClient` methods

| Method | Description |
|--------|-------------|
| `async_connect()` | Connect to the device |
| `async_wait_until_ready()` | Wait for initial handshake to complete |
| `refresh(zone=None)` | Query zone state (all zones if omitted) |
| `async_subscribe(callback)` | Register callback for zone state changes |
| `async_power_on(zone)` | Power on a zone |
| `async_power_off(zone)` | Power off a zone |
| `power_on_all_zones()` | Power on all zones |
| `power_off_all_zones()` | Power off all zones |
| `async_set_source(zone, source)` | Set active source for a zone |
| `async_set_volume(zone, volume)` | Set volume (0–60) |
| `async_volume_up(zone)` | Increment volume |
| `async_volume_down(zone)` | Decrement volume |
| `async_mute(zone)` | Mute a zone |
| `async_unmute(zone)` | Unmute a zone |
| `async_toggle_mute(zone)` | Toggle mute |
| `async_set_bass(zone, bass)` | Set bass |
| `async_set_treble(zone, treble)` | Set treble |
| `async_set_balance(zone, balance)` | Set balance |
| `async_set_dnd(zone, dnd)` | Set Do Not Disturb (Lync only) |
| `async_query_zone_name(zone)` | Query zone name from controller (Lync only) |
| `async_query_source_name(source)` | Query source name from controller (Lync only) |
| `async_set_zone_name(zone, name)` | Set zone name on controller (Lync only) |
| `async_set_source_name(source, name)` | Set source name on controller (Lync only) |
| `get_zone(zone)` | Return cached `ZoneDetail` for a zone |
| `get_zone_name(zone)` | Return cached zone name |
| `get_source_name(source)` | Return cached source name |
| `get_source_names() -> dict[int, str]` | Every source name the controller has reported. Unlike `get_source_name(n)`, it never invents a `"Source N"` placeholder, so the result is safe to persist. |
| `get_zone_names() -> dict[int, str]` | The same, for zone names (Lync only). |
| `get_zone_count()` | Return number of zones for this model |
| `get_source_count()` | Return number of sources for this model |
| `disconnect()` | Close the connection |

### Behavior change in 0.1.8

Commands and `refresh()` now raise `HtdConnectionError("not connected")` when the client is
disconnected. Previously they raised `AttributeError: 'NoneType' object has no attribute
'write'`. Direct consumers catching `AttributeError` must switch to `HtdConnectionError`.

`connection_made` and `connection_lost` now broadcast to subscribers with `zone=None`, so a
subscriber is notified of transport state changes and not only of incoming data. Subscribers
that assumed a `None` zone meant "data arrived for an unknown zone" should re-read state from
the client rather than assuming a zone payload is present.

## Contributing

[Poetry](https://python-poetry.org/docs/#installation) is used to manage dependencies and run tests.

```bash
poetry install
poetry run pytest
```

## License

MIT — see [LICENSE](LICENSE) for details.

## Credits

- [hikirsch/python-htd](https://github.com/hikirsch/python-htd) — original library by Adam Kirschner
- [kingfetty/python-htd](https://github.com/kingfetty/python-htd) — Lync protocol support
