# Home Sweet Home — Home Assistant Constitution

## Core Principles

### I. Household Integration Boundary

This repository owns Home Assistant configuration, connected devices, voice surfaces, automations,
presence, and notifications. It does not own the TV dashboard, module implementations, MCP agent
logic, or LLM orchestration.

### II. Local-First and Private by Default

Home Assistant MUST run on household infrastructure where practical. Cloud integrations, remote
access, external voice services, and telemetry are opt-in, documented, and minimized. Secrets,
tokens, device identifiers, and private household data MUST NOT be committed.

### III. Configuration as Code

Changes to integrations, automations, scripts, scenes, dashboards, and notification policy MUST be
represented in reviewable configuration whenever Home Assistant supports it. UI-only changes must
be exported or documented before they become operational dependencies.

### IV. Safe Automation

Automations MUST be explicit about triggers, conditions, targets, and failure behavior. Actions with
physical, financial, privacy, or destructive consequences MUST require an explicit confirmation or
an independently verified condition.

### V. Observable Recovery

The system MUST provide health visibility for Home Assistant, the agent, and critical integrations.
Backups, restore procedures, upgrade procedures, and failure behavior MUST be documented and tested.

### VI. Human-Centered Voice Access

Voice interactions MUST provide understandable confirmation, error, and unavailable-service
responses. The assistant MUST NOT claim that an action succeeded when the underlying service did
not confirm it.

## Technology Standards

- Home Assistant is the household automation platform.
- Assist is the preferred voice interface for phone and supported home voice hardware.
- Google Home integrations are optional external surfaces, not the source of truth.
- The Home Sweet Home Agent is accessed through a documented private interface.
- Secrets use Home Assistant's secret mechanism or deployment environment variables.
- Configuration validation and real-device smoke tests are required before merge.

## Repository Boundaries

- `home-sweet-home-dashboard` owns the TV dashboard.
- `home-sweet-home-modules` owns module implementations and published backends.
- `home-sweet-home-agent` owns MCP sessions, LLM calls, authorization, and conversation behavior.
- This repository owns household integration and presentation through Home Assistant.

## Governance

This constitution governs this repository. Material amendments require documentation of the reason,
the affected household behavior, migration steps, and explicit approval before implementation.
