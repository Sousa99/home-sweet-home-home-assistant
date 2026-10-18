# Home Assistant Documentation

Document hardware-specific pairing, Google Home setup, Assist voice pipelines, notification
delivery, backups, and recovery procedures here as they are established.

## macOS ZBT-2 development setup

Docker Desktop on macOS cannot directly pass the ZBT-2's CDC-ACM serial interface into a
container. For development, run `scripts/zbt2-serial-bridge.py` on the Mac. It exposes the Mac
serial device through RFC2217 at `rfc2217://host.docker.internal:6638`.

Start it from the repository root:

```bash
uv run scripts/zbt2-serial-bridge.py
```

To keep it running and restart it automatically on macOS:

```bash
scripts/install-zbt2-launch-agent.sh
```

The LaunchAgent writes logs to `/tmp/home-sweet-home-zbt2-bridge.log`. The ZBT-2 must be connected
before or after login; the bridge retries through `launchd` when the serial device is unavailable.

The bridge uses 460800 baud and RTS/CTS hardware flow control, matching the ZBT-2 Zigbee firmware.
It binds to localhost and supports one Home Assistant connection at a time. Keep the process
running while ZHA is using the coordinator. Set `ZBT2_SERIAL_PORT` or pass `--serial-port` if more
than one USB serial device is connected.

In the ZHA setup flow, use the bridge URL as the serial device path. Select the Silicon Labs EZSP
radio type, 460800 baud, and hardware flow control if those fields are shown.

## Connected Zigbee devices

### Living Room climate sensor

- Device: SONOFF `SNZB-02D`
- Home Assistant name: `Living Room Climate Sensor`
- Integration: ZHA through the Home Assistant Connect ZBT-2
- Entities: `sensor.living_room_climate_sensor_temperature`,
  `sensor.living_room_climate_sensor_humidity`, and
  `sensor.living_room_climate_sensor_battery`

### Living Room window status

- Device: SONOFF `SNZB-04PR2`
- Home Assistant name: `Window Status`
- Area: `Living Room`
- Integration: ZHA through the Home Assistant Connect ZBT-2
- Opening entity: `binary_sensor.main_area_window_status`
- Battery entity: `sensor.main_area_window_status_battery`
- Dashboard: Home Assistant UI-managed `Security`

The Security dashboard is managed through Home Assistant's UI and is not represented as committed
YAML in this repository. Keep its entity dependencies documented here and include the dashboard in
Home Assistant backups.

## Development remote access

The current development host is a macOS machine running Home Assistant Container through Docker
Desktop. Tailscale is installed on the Mac and on the household phones.

### Current access path

- Home Assistant is published on host port `8123`.
- Tailscale reaches the Mac host; Docker Desktop forwards port `8123` to Home Assistant.
- Access uses the Mac's Tailscale IP or MagicDNS hostname with the `http://` scheme and port `8123`.
- Tailscale Serve is not currently configured.
- HTTPS is intentionally deferred until the permanent server is deployed.

Do not commit the Tailscale IP, tailnet name, account details, auth keys, or phone identifiers.
Retrieve the current address with `tailscale ip -4` or from the Tailscale admin console.

### Supported network changes

The Mac can move between the household phones' hotspots and later home Wi-Fi. The remote URL stays
the same while the Mac is online on Tailscale. If the Mac has no internet connection, remote access
is unavailable, but local Home Assistant, Zigbee, and automations continue to operate.

Both Tailscale and Home Assistant authentication are required. Each household member should use a
separate Home Assistant account; do not share credentials.

### Permanent server plan

When Home Assistant moves to the always-on Linux server:

1. Install Tailscale as a host background service.
2. Restore Home Assistant from the tested backup.
3. Attach the ZBT-2 directly to the Linux host and replace the macOS serial bridge with a stable
   `/dev/serial/by-id/...` mapping.
4. Reconnect the phones to the server's Tailscale hostname.
5. Configure Tailscale Serve HTTPS only after choosing a neutral server hostname.
6. In Home Assistant, configure the HTTP reverse-proxy trust settings for the final Serve proxy.

Enabling Tailscale HTTPS publishes the server and tailnet names in Certificate Transparency logs.
Review those names before enabling certificates. Tailscale is an intentional cloud dependency for
coordination and remote access; Zigbee control remains local.
