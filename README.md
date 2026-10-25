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
└── scenes.yaml          # Named device states
```

Runtime state, databases, media, and credentials belong in the Home Assistant data directory and
are excluded from this repository. The `backups/` directory contains recovery documentation, not
private backup archives.

## Home Sweet Home Agent integration

The agent is configured as a private service endpoint. Its responsibility is to translate natural
language into authorized MCP tool calls. Home Assistant is responsible for presenting the result
through Assist, notifications, or announcements.

The integration must support:

- Phone Assist requests
- Home voice requests
- Explicit confirmation for destructive actions
- Proactive notifications such as bus departure and task reminders
- Health reporting when the agent or module MCPs are unavailable

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
