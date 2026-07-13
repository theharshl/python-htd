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
| `get_zone_count()` | Return number of zones for this model |
| `get_source_count()` | Return number of sources for this model |
| `disconnect()` | Close the connection |

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
