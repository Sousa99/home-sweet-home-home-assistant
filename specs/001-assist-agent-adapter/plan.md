# Implementation Plan: Assist Conversation Adapter for the Home Sweet Home Agent

**Branch**: `001-assist-agent-adapter` | **Date**: 2026-11-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-assist-agent-adapter/spec.md`

## Summary

Add a thin Home Assistant custom integration that registers a conversation agent and forwards Assist
text and voice requests to the Home Sweet Home agent's private HTTP contract. The adapter holds no
LLM, MCP, authorization, or tool-policy logic: it relays text, conversation identifiers, and bearer
credentials, maps completed/failed/confirmation responses into Assist speech, and keeps confirmation
tokens per conversation until they are approved, declined, used, or expire. Configuration is created
through a config flow, validated against the agent's health endpoint, and stored only in the
PVC-backed config entry.

## Technical Context

**Language/Version**: Python 3.14 (required by Home Assistant 2026.10.2)

**Primary Dependencies**: Home Assistant `conversation` integration, Home Assistant shared
`aiohttp` client session via `async_get_clientsession`, Home Assistant config-entry and intent
helpers. No third-party runtime dependencies.

**Storage**: Home Assistant config entry in `.storage` on the PVC (agent URL and bearer token).
Pending confirmations are in-memory only and bounded by the agent's 120-second TTL. No database or
tracked YAML is added.

**Testing**: `pytest` with `pytest-homeassistant-custom-component`, using its `hass`,
`enable_custom_integrations`, `MockConfigEntry`, and mocked HTTP client fixtures. Tests require no
live agent or cluster.

**Target Platform**: Home Assistant 2026.10.2 container on Linux, deployed in the
`home-sweet-home` namespace of the k3s cluster. Local development uses the Compose image.

**Project Type**: Home Assistant custom integration plus its test suite.

**Performance Goals**: Typical replies are bounded by the agent's 30-second model budget plus tool
execution. The adapter enforces a 90-second total request bound and a 10-second configuration
health check. A single household deployment serves a small number of concurrent conversations.

**Constraints**: No MCP client, LLM call, prompt, or tool policy in Home Assistant. The token is
never logged or tracked. Requests use the private in-cluster service only; no public ingress.
Confirmation approvals execute at most once and never after local expiry. The component must be
loaded from the seeded configuration after pod start.

**Scale/Scope**: Two household languages (Portuguese and English), a handful of voice surfaces,
and low request volume. Phase 1 exposes read/write tools only; destructive actions are excluded by
the agent caller permission set.

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

| Principle | Gate | Status |
| --- | --- | --- |
| I. Household Integration Boundary | Adapter forwards to the agent; no LLM, MCP, or tool policy is implemented here. | Pass |
| II. Local-First and Private by Default | Private in-cluster endpoint only; token lives in `.storage`, never Git, YAML, or logs. | Pass |
| III. Configuration as Code | Component and tests are tracked; the UI-created config entry and Assist agent selection are documented in `docs/`. | Pass |
| IV. Safe Automation | Phase 1 is read/write only; P2 requires explicit confirmation and expiry handling. | Pass |
| V. Observable Recovery | `/healthz` validation, clear unavailable/error speech, and documented rebuild/rollout/restore steps. | Pass |
| VI. Human-Centered Voice Access | Errors are spoken, no success is invented, and the 120-second voice confirmation constraint is documented. | Pass |

No violations. Complexity Tracking is not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-assist-agent-adapter/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 validation guide
├── contracts/
│   ├── agent-http.md    # Consumed agent HTTP contract and mappings
│   └── conversation-entity.md # Home Assistant conversation entity contract
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
config/
└── custom_components/
    ├── __init__.py
    └── home_sweet_home_agent/
        ├── __init__.py
        ├── const.py
        ├── config_flow.py
        ├── conversation.py
        ├── manifest.json
        ├── strings.json
        └── translations/
            └── en.json

tests/
├── conftest.py
├── test_config_flow.py
├── test_conversation.py
└── test_confirmation.py

pytest.ini
requirements_test.txt
docs/
└── README.md            # Extended with agent adapter, token, and pipeline guidance
README.md                # Updated integration overview and rollout path
```

**Structure Decision**: The integration lives under the tracked `config/custom_components/` tree so
the existing Dockerfile `COPY config/ /config-seed/` includes it automatically. Tests live at the
repository root because there is no existing Python package layout. `pytest.ini` and
`requirements_test.txt` define the isolated test environment.

### Key Design Decisions

- **Conversation entity**: Implement `ConversationEntity._async_handle_message` with the Home
  Assistant `ChatLog` so the agent integrates with current Assist behavior. `supported_languages`
  is `MATCH_ALL`; `supported_features` is `ConversationEntityFeature.CONTROL`.
- **Conversation continuity**: Derive the effective conversation ID from
  `ConversationInput.conversation_id`, falling back to `chat_log.conversation_id`. Send it as
  `conversationId` on every request and return it in `ConversationResult`.
- **HTTP client**: Use `async_get_clientsession(hass)` for connection pooling and test mocking.
  Apply `aiohttp.ClientTimeout(total=90)` to conversation and confirmation calls and a short timeout
  to health validation.
- **Setup validation**: `GET {base_url}/healthz` with the bearer header. Map 200 to success,
  401/403 to `invalid_auth`, timeout to `timeout`, and transport/non-2xx failures to
  `cannot_connect`. Because the agent contract marks probes as unauthenticated, a health 200 proves
  reachability but not token validity; the first authenticated `/conversation` 401/403 is surfaced
  as a clear spoken credential error. This contract limitation is documented in research and docs.
- **Error mapping**: Return `IntentResponse` with `IntentResponseResponseType.ERROR` and speech for
  every failure. Include the agent's `error.code` and `message` for `status: failed`. Never return a
  normal response for an unknown status.
- **Phase 1 scope**: No destructive tools are advertised because the caller token has `read,write`
  only. Home Assistant never opens an MCP session.
- **P2 confirmation**: Store one `PendingConfirmation` per conversation in the entity (token, tool,
  argument preview, expiry, language). Recognize yes/no in English and Portuguese, call
  `POST /confirm`, clear the pending entry before awaiting the call to enforce single use, reject
  approvals after local expiry, and treat ambiguous follow-ups as a clarification request.
  Pending state is lost on restart; expired agent tokens are safe to forget.
- **Image and deployment**: No Dockerfile change is needed because `config/` is copied wholesale.
  The publish workflow already triggers on `config/**`. Rebuild, publish, then let Flux roll out the
  new image and restart the pod so the seed refreshes `/config` without touching `.storage`.

## Phase 0: Outline & Research

Research is captured in [research.md](./research.md). It resolves:

- Current Home Assistant conversation entity API and chat-log usage.
- Configuration validation behavior given unauthenticated probes.
- Error, timeout, and connection mapping that keeps the Assist pipeline alive.
- Confirmation follow-up parsing, single-use enforcement, and expiry handling.
- Test strategy with `pytest-homeassistant-custom-component` and mocked HTTP.
- Token creation, rotation, secret storage, and pipeline-selection documentation.

**Output**: `research.md` with all decisions and alternatives.

## Phase 1: Design & Contracts

- [data-model.md](./data-model.md) defines config entry data, runtime client state, response
  variants, and pending confirmation lifecycle.
- [contracts/agent-http.md](./contracts/agent-http.md) documents the consumed agent endpoints,
  authentication, payloads, response mapping, and timeout rules.
- [contracts/conversation-entity.md](./contracts/conversation-entity.md) documents the Home
  Assistant conversation platform contract exposed by the integration.
- [quickstart.md](./quickstart.md) documents token creation, config entry setup, pipeline selection,
  test execution, image build, and Flux rollout validation.

**Output**: `data-model.md`, `contracts/*`, `quickstart.md`.

## Post-Design Constitution Check

The design remains within the household integration boundary, stores no secret in Git or YAML,
documents UI-only state, enforces confirmation and expiry, and provides spoken failure behavior.
All gates still pass with no exceptions.

## Complexity Tracking

No constitution violations. No additional projects, abstractions, or persistent stores are
introduced beyond the custom integration and its tests.
