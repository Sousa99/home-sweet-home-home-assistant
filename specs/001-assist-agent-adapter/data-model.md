# Data Model: Assist Conversation Adapter for the Home Sweet Home Agent

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

The adapter has no database. Its data consists of a persistent Home Assistant config entry, a
runtime HTTP client, transient conversation state, and short-lived pending confirmations.

## Config Entry Data

The Home Assistant config entry is stored in `.storage/core.config_entries` on the PVC.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `url` | string | Yes | Base URL of the agent, for example `http://agent.agent.svc.cluster.local:3400`. Stored without a trailing slash. |
| `token` | string (secret) | Yes | Plaintext bearer token for the dedicated `home-assistant` caller. Never logged, never written to tracked YAML. |

**Validation rules**:

- `url` must be an absolute `http` or `https` URL with a host.
- `token` must be a non-empty string.
- The config flow calls `GET {url}/healthz` with the bearer header and a 10-second timeout.
- 200 creates the entry; 401/403 produces `invalid_auth`; timeout produces `timeout`; transport
  errors or unexpected statuses produce `cannot_connect`.
- The URL is normalized by removing trailing slashes.
- Duplicate entries for the same normalized URL are rejected by unique ID.

**Secret handling rules**:

- The token is passed only in the `Authorization` header.
- The token is never included in log messages, exception text, diagnostics, or test fixtures that
  are committed with real values.
- Configuration validation errors never echo the token.

## Runtime Client

Created when the config entry is set up and stored on the entry runtime data.

| Field | Type | Description |
| --- | --- | --- |
| `base_url` | string | Normalized agent URL from the config entry. |
| `token` | string | Bearer token from the config entry. |
| `session` | `aiohttp.ClientSession` | Home Assistant shared client session. |
| `conversation_timeout` | timeout | 90 seconds for `/conversation` and `/confirm`. |
| `health_timeout` | timeout | 10 seconds for `/healthz`. |

The client is not used during entry setup. It is created without contacting the agent so a
temporarily unavailable agent does not block Home Assistant startup.

## Conversation State

A conversation is identified by the Home Assistant conversation ID.

| Field | Type | Description |
| --- | --- | --- |
| `conversation_id` | string | Derived from `ConversationInput.conversation_id`, falling back to `chat_log.conversation_id`. Sent as `conversationId`. |
| `language` | string | `ConversationInput.language`, used to choose Portuguese or English error and confirmation prompts. |
| `pending_confirmation` | object or none | At most one `PendingConfirmation` per conversation. |

Conversation state itself is not persisted; only the config entry and the Assist pipeline selection
are stored in `.storage`.

## Pending Confirmation

Created when the agent returns `status: confirmation_required`. Held in memory on the conversation
entity.

| Field | Type | Source | Description |
| --- | --- | --- | --- |
| `token` | string | `confirmation.token` | Single-use token to send to `/confirm`. |
| `tool` | string | `confirmation.tool` | Tool name shown to the user. |
| `arguments_preview` | object/string | `confirmation.argumentsPreview` | Human-readable preview of the proposed action. |
| `expires_at` | datetime | `confirmation.expiresAt` | Authoritative agent expiry; currently 120 seconds after issue. |
| `created_at` | datetime | Adapter clock | Used for diagnostics and local expiry checks. |
| `language` | string | Current request | Language for follow-up prompts and errors. |

**State transitions**:

```text
(none) --confirmation_required--> pending
pending --affirmative + POST /confirm(approve)--> resolved (removed before call)
pending --negative + POST /confirm(reject)--> resolved (removed before call)
pending --local expiry--> expired (removed; no approve call)
pending --ambiguous follow-up--> pending (clarification returned)
pending --replacement confirmation_required--> pending (old token discarded)
```

**Rules**:

- At most one pending confirmation exists per conversation.
- The pending record is deleted before awaiting `/confirm`, enforcing at-most-once approval inside
  Home Assistant.
- If `expires_at` is in the past, approval is refused locally and no action is requested.
- A replayed approval after a resolved decision finds no pending record and is treated as a new
  request, not a second approval.
- Pending state is lost on restart; the agent's token expiry is the safety net.
- The token is never logged.

## Agent Outcome Model

The adapter recognizes exactly these response shapes from `POST /conversation` and
`POST /confirm`.

### Completed

```json
{
  "status": "completed",
  "reply": "The living room is 21 degrees.",
  "trace": []
}
```

| Field | Type | Adapter behavior |
| --- | --- | --- |
| `status` | `"completed"` | Return `reply` as normal speech. |
| `reply` | string | Must be non-empty; empty is treated as a malformed response. |
| `trace` | array | Ignored by Home Assistant; not logged with sensitive content. |

### Confirmation Required (P2)

```json
{
  "status": "confirmation_required",
  "reply": "Turning off the heater will make the room cold. Confirm?",
  "confirmation": {
    "token": "single-use-token",
    "tool": "set_heater_power",
    "argumentsPreview": {"power": "off"},
    "expiresAt": "2026-11-07T12:00:00.000Z"
  },
  "trace": []
}
```

| Field | Adapter behavior |
| --- | --- |
| `status` | Create or replace the pending confirmation for the conversation. |
| `reply` | Return as speech. |
| `confirmation.token` | Store for the follow-up; never log. |
| `confirmation.tool` | Store for user-facing context. |
| `confirmation.argumentsPreview` | Store for user-facing context; do not execute anything. |
| `confirmation.expiresAt` | Store as the expiry boundary. |

### Failed

```json
{
  "status": "failed",
  "error": {
    "code": "llm_timeout",
    "message": "The model did not respond in time."
  }
}
```

| Field | Adapter behavior |
| --- | --- |
| `status` | Return an error response, never a normal response. |
| `error.code` | Include in the spoken error so the user and logs can identify the class of failure. |
| `error.message` | Include a user-facing portion; do not invent success. |

### Transport and HTTP Failures

| Condition | Spoken error class |
| --- | --- |
| HTTP 401 or 403 | Credential rejected; update the integration configuration. |
| HTTP 5xx | Agent unavailable. |
| Other non-2xx | Unexpected response from the agent. |
| `asyncio.TimeoutError` / client timeout | Agent took too long. |
| `aiohttp.ClientError` or DNS/connection failure | Agent cannot be reached. |
| Invalid JSON or unknown/missing `status` | Unexpected response from the agent. |
| Unknown confirmation token or expired pending | Confirmation expired or no longer pending. |

All failures return an `IntentResponseResponseType.ERROR` response with understandable speech and
leave the conversation usable.
