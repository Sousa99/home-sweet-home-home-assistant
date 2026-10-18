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
