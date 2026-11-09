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

## Home Sweet Home Agent conversation adapter

Assist text and voice requests use the tracked custom integration at
`config/custom_components/home_sweet_home_agent/` as their conversation agent. The integration is a
thin HTTP adapter over the agent's private in-cluster service; it does not connect to module MCP
servers, call an LLM, or implement prompt or tool policy.

### Create the dedicated caller token

Run this in the `home-sweet-home-agent` repository, not in this repository:

```bash
pnpm token:generate -- --caller-id home-assistant --permissions read,write
```

The command prints a plaintext token and its SHA-256 hash entry. Only the hash map belongs in the
cluster `agent-auth` Secret (the `AGENT_AUTH_TOKENS` value expected by the agent). Never commit the
plaintext token, and do not place it in `secrets.yaml`, tracked YAML, image layers, or logs.

Rotate the previously shared token when introducing the dedicated Home Assistant caller. After the
rotated Secret is applied, restart or roll out the agent and confirm it is healthy.

### Configure the integration

1. Rebuild and publish the Home Assistant image. The existing `COPY config/ /config-seed/` includes
   the custom component, so no Dockerfile change is needed. Let Flux reconcile the new image tag and
   restart the Home Assistant pod so the seed refreshes `/config`; `.storage` and databases on the
   PVC are preserved.
2. In Home Assistant, open **Settings → Devices & services → Add integration**.
3. Select **Home Sweet Home Agent**.
4. Enter the private agent URL `http://agent.agent.svc.cluster.local:3400` and the plaintext token
   from the previous step.
5. Submit. Setup checks `GET /healthz` and reports `cannot_connect`, `invalid_auth`, or `timeout`
   for invalid configurations.

The token is stored only in the config entry in `.storage`, which is backed by the PVC. It is not
written to tracked YAML and must not be added to the repository. Because the agent's probes are
unauthenticated, a successful setup proves reachability and best-effort authorization; a revoked or
rotated token is reported as a spoken credential error on the next conversation request.

### Select the Assist conversation agent

1. Open **Settings → Voice assistants**.
2. Edit the default Assist pipeline.
3. Set **Conversation agent** to **Home Sweet Home Agent**.
4. Save, then test through the Home Assistant chat and a voice satellite.

The pipeline selection is stored in `.storage` on the PVC, not in tracked YAML. Include it in
backups and re-select the agent after a restore if the stored selection is missing.

### Behavior and failure handling

- Completed requests return the agent's reply as speech.
- Agent `failed` responses return a spoken error that includes the agent's error code and message.
- Connection failures, HTTP 401/403, 5xx responses, malformed payloads, and timeouts produce clear
  spoken errors without crashing or hanging the Assist pipeline.
- Conversation and confirmation requests use a 90-second bound, covering the agent's 30-second model
  timeout plus tool execution.
- Phase 1 grants the caller `read,write`; destructive tools are not advertised.
- Phase 2 handles `confirmation_required` by prompting for yes/no and calling `POST /confirm`.
  Approvals execute exactly once; declined, expired, and replayed confirmations execute nothing.

Confirmation tokens currently expire after 120 seconds. Voice users must answer promptly. If the
confirmation expires, the assistant asks the user to repeat the request; it does not retry
automatically.

### Troubleshooting

- If the integration is missing after rollout, confirm the pod restarted and
  `/config/custom_components/home_sweet_home_agent/manifest.json` exists in the container.
- If setup reports `cannot_connect`, confirm the pod can resolve and reach
  `agent.agent.svc.cluster.local:3400`.
- If requests report a credential error, rotate the token again and update the config entry with
  the new plaintext value. Removing and re-adding the entry replaces the stored token.
- If Assist still uses the wrong agent, re-select **Home Sweet Home Agent** in the pipeline.
