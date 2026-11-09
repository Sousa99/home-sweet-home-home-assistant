# Home Sweet Home — Home Assistant

The household automation and voice layer for Home Sweet Home. This repository contains the
Home Assistant deployment configuration, connected-device setup, voice surfaces, automations,
and notification policies. It is intentionally separate from the TV dashboard and the MCP agent.

```text
┌──────────────────────────────────────────────────────────────┐
│ Home Sweet Home · Home Assistant                             │
├──────────────────────┬───────────────────────────────────────┤
│ Phone                 │ Home                                  │
│ HA Companion + Assist│ Voice satellites / Google Home bridge  │
├──────────────────────┴───────────────────────────────────────┤
│ Devices · Automations · Notifications · Presence              │
└──────────────────────────────────────────────────────────────┘
```

## Responsibilities

| Area | Owned here |
| ---- | ---------- |
| Home Assistant | Deployment, configuration, upgrades, backups |
| Devices | Pairing and integrations for household devices |
| Voice | Assist pipelines, voice satellites, phone voice access |
| Speakers | Google Home and other speaker integrations |
| Automations | Household rules and scheduled actions |
| Notifications | Phone notifications, announcements, and delivery policy |
| MCP agent | Connected as an external service; implemented elsewhere |

## Architecture

```text
HA Companion App ─┐
Voice satellites ──┼── Home Assistant ─── Home Sweet Home Agent
Google Home ──────┘          │                         │
                             └── devices               └── module MCP servers
```

Home Assistant is the household integration boundary. The Home Sweet Home Agent owns LLM
conversation behavior, MCP sessions, authorization, and tool-call confirmation. Home Assistant
does not connect independently to every module MCP server in the recommended production setup.

## Quick start

The deployment method is intentionally environment-specific. Start by installing a supported Home
Assistant distribution on the home host, then copy this repository's configuration into the active
Home Assistant configuration directory.

```bash
cp .env.example .env
# Configure secrets outside Git before starting Home Assistant.
docker compose up -d
```

The exact host, storage, backup, and hardware requirements are documented in [`docs/`](docs/).
Do not commit `secrets.yaml`, device tokens, OAuth credentials, or generated Home Assistant state.

## Cluster deployment

Production runs in the `home-sweet-lab` k3s cluster. This repository publishes the image that
cluster consumes; the cluster owns the ZBT-2 and the persistent Home Assistant state. The Compose
quick start is retained for local development and recovery, not as the primary deployment.

## Container image

Every push to `main` that changes the tracked configuration publishes an image to GHCR:

```text
ghcr.io/sousa99/home-sweet-home-home-assistant:main-<timestamp>-<sha7>
```

The image is built from the official Home Assistant image and contains only tracked configuration at
`/config-seed/`. It never contains `.storage`, databases, backups, secrets, media, or logs. The
workflow is in [`.github/workflows/publish-image.yaml`](.github/workflows/publish-image.yaml).

The image is consumed by the `home-sweet-lab` cluster. That repository seeds the tracked YAML into
`/config`, restores private state from an uploaded bundle, and runs Home Assistant with a persistent
volume. The image package must stay public so the cluster can pull it without credentials.

The image also contains the tracked `config/custom_components/home_sweet_home_agent/` integration.
`COPY config/ /config-seed/` includes it automatically, and the cluster seed installs it into
`/config/custom_components/` on pod start. Rebuild the image and let Flux roll out the new tag after
changing the adapter; `.storage`, databases, and backups on the PVC are preserved.

Home Assistant 2026.8+ stores HTTP server settings in `.storage/http` and deprecates the `http:`
block in `configuration.yaml`. The image includes `scripts/fix-http-proxy.py`, which the cluster runs
as an init container to enable `X-Forwarded-For` and trust the ingress proxy. Do not re-add the
deprecated `http:` block.

Building locally:

```bash
docker build -t home-assistant-config:local .
docker run --rm home-assistant-config:local ls /config-seed
```

## Configuration layout

```text
config/
├── configuration.yaml   # Core integrations and includes
├── automations.yaml     # Household automations
├── scripts.yaml         # Reusable actions
├── scenes.yaml          # Named device states
└── custom_components/
    └── home_sweet_home_agent/   # Assist conversation adapter
```

Runtime state, databases, media, and credentials belong in the Home Assistant data directory and
are excluded from this repository. The `backups/` directory contains recovery documentation, not
private backup archives.

## Home Sweet Home Agent integration

The agent is configured as a private service endpoint. Its responsibility is to translate natural
language into authorized MCP tool calls. Home Assistant is responsible for presenting the result
through Assist, notifications, or announcements.

The repository ships a thin conversation adapter at
`config/custom_components/home_sweet_home_agent/`. Under
`Settings → Devices & services → Add integration`, configure the private agent URL
(`http://agent.agent.svc.cluster.local:3400`) and the dedicated bearer token. The adapter forwards
Assist text and voice requests to `POST /conversation`, reuses the Home Assistant conversation ID
for the exchange, and returns completed replies or clear spoken errors.

The adapter is an HTTP relay only. It does not hold an MCP session, call an LLM, or implement prompt
or tool policy. Phase 1 exposes read and write actions through the agent's `read,write` caller
permissions; destructive tools are not advertised. Phase 2 resolves `confirmation_required`
responses through `POST /confirm` with single-use approvals and expiry handling.

Configuration and operating rules:

- The token is stored only in the Home Assistant config entry in `.storage` on the PVC. It is never
  committed, written to YAML, or logged.
- Setup validates `GET /healthz` with a short timeout and rejects unreachable or unauthorized
  configurations. Because the agent probes are unauthenticated, the first authenticated request
  also reports revoked credentials clearly.
- Conversation and confirmation calls use the shared Home Assistant HTTP session with a 90-second
  bound, covering the agent's model timeout plus tool execution.
- Timeouts, connection failures, HTTP 401/403, malformed responses, and agent `failed` outcomes all
  produce spoken errors; the pipeline does not hang or claim success.
- Confirmation tokens currently expire after 120 seconds. Voice users must answer promptly, and an
  expired confirmation requires repeating the request.
- The Assist pipeline's conversation-agent selection lives in `.storage` on the PVC, not in tracked
  YAML. Include it in backups and re-select **Home Sweet Home Agent** after a state restore if
  needed.

See [`docs/README.md`](docs/README.md) for token creation, agent `agent-auth` Secret handling,
rotation of the previously shared token, pipeline selection, and rollout steps.

## Quality checks

Before applying configuration changes:

```bash
docker compose config
docker compose up -d
```

Then validate the configuration from the Home Assistant UI and test affected devices, voice
pipelines, automations, notifications, and recovery behavior on real hardware.

## Related repositories

| Repository | Purpose |
| ---------- | ------- |
| `home-sweet-home-dashboard` | TV / large-screen dashboard and local module deployment |
| `home-sweet-home-modules` | Module implementations and published MCP backends |
| `home-sweet-home-agent` | Central MCP host, LLM integration, and adapters |

## Project status

This repository is the foundation for the Home Assistant layer. Device-specific integrations,
voice hardware, and notification policies should be added incrementally and documented alongside
their configuration.
