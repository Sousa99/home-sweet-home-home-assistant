# Research: Assist Conversation Adapter for the Home Sweet Home Agent

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-11-07

## Decision: Use the current ConversationEntity chat-log API

**Decision**: Implement a `ConversationEntity` subclass that overrides
`_async_handle_message(user_input, chat_log)` rather than the older `async_process` method.
Register it through a conversation platform forwarded from the config entry. Set
`supported_languages = MATCH_ALL` and `supported_features = ConversationEntityFeature.CONTROL`.

**Rationale**: Home Assistant's current conversation entity contract creates the chat session and
chat log before calling the entity. Using `_async_handle_message` gives the integration a supported
place to add assistant content and to return `ConversationResult`, while `supported_features =
CONTROL` correctly tells Assist that the agent can act on devices. `MATCH_ALL` avoids per-language
agent configuration for Portuguese and English.

**Alternatives considered**:

- Older `async_process` override: still works but bypasses chat-log handling and is no longer the
  recommended pattern.
- A custom `AbstractConversationAgent`: lower-level and unnecessary for an entity-backed config
  entry.
- Restricting `supported_languages` to `["en", "pt"]`: rejected because Home Assistant language tags
  can include regional variants and `MATCH_ALL` is explicitly allowed by the requirements.

## Decision: Derive and reuse one conversation identifier per exchange

**Decision**: Use `ConversationInput.conversation_id` when present, otherwise
`chat_log.conversation_id`. Send it as `conversationId` in the `/conversation` body and return the
same value in `ConversationResult.conversation_id`.

**Rationale**: The agent binds confirmation tokens to the caller and conversation ID. Reusing the
HA-issued identifier keeps multi-turn context coherent and makes the confirmation follow-up resolve
against the same conversation. `chat_log.conversation_id` covers the case where the input has no ID
yet.

**Alternatives considered**:

- Generate a new UUID per request: breaks multi-turn context and confirmation binding.
- Omit `conversationId` on the first call and rely on the agent: the contract allows it, but keeping
  the HA identifier in sync is more predictable and testable.

## Decision: Validate reachability through `/healthz`; token validity is confirmed on first use

**Decision**: During the config flow, call `GET {base_url}/healthz` with
`Authorization: Bearer <token>` and a 10-second timeout. Treat 200 as success, 401/403 as
`invalid_auth`, timeouts as `timeout`, and transport errors or other statuses as `cannot_connect`.
Because the agent contract states probes are unauthenticated, also map a 401/403 from the first
authenticated `/conversation` call to a clear spoken credential error.

**Rationale**: The agent exposes only `/healthz` and `/readyz` without required authentication.
There is no harmless authenticated endpoint that proves a token without invoking the conversation
pipeline. Sending the bearer header to `/healthz` lets the adapter reject agents that do enforce
authorization on the probe, while keeping setup side-effect free. The first real request is the
first guaranteed authentication check.

**Alternatives considered**:

- Call `POST /conversation` during setup with a probe message: rejected because it invokes the LLM
  and tools, may have side effects, and is not a health check.
- Accept any 200 from `/healthz` without attempting token validation: rejected because it gives no
  chance to catch an unauthorized setup early.
- Add a new agent endpoint: out of scope; the agent contract is owned by `home-sweet-home-agent`.

**Documentation requirement**: Explain that setup validates the URL and best-effort credential, and
that a rotated or revoked token is reported on the next conversation request.

## Decision: Shared Home Assistant HTTP session with a 90-second bound

**Decision**: Use `homeassistant.helpers.aiohttp_client.async_get_clientsession(hass)` and pass
`aiohttp.ClientTimeout(total=90)` to `/conversation` and `/confirm`. Use a shorter timeout for
`/healthz`.

**Rationale**: The agent's model timeout is 30 seconds, with additional tool execution time. A
90-second bound allows normal completion without letting Assist hang indefinitely. The shared HA
session is supported, pooled, and mockable in tests.

**Alternatives considered**:

- A dedicated `aiohttp.ClientSession`: rejected because Home Assistant owns connection lifecycle
  and the shared session is the documented pattern.
- No timeout: rejected because it can hang a voice pipeline and violate the failure requirements.
- 30-second timeout: too short for model plus tool work.

## Decision: Map every agent outcome to explicit speech, never inferred success

**Decision**:

| Agent outcome | Adapter behavior |
| --- | --- |
| `completed` with non-empty `reply` | Add assistant content to the chat log and return a normal `IntentResponse` with the reply as speech. |
| `failed` with `error.code` / `error.message` | Return an error `IntentResponse` with a user-facing message that includes the code and message. |
| `confirmation_required` | Store the pending confirmation and return the agent's reply as speech. (P2) |
| HTTP 401/403 | Spoken credential error instructing the user to update the integration. |
| Timeout | Spoken "took too long" response; pipeline remains usable. |
| Connection/transport error | Spoken "cannot reach the assistant" response. |
| Malformed or unknown status | Spoken unexpected-response error. |
| Missing/empty reply on `completed` | Treated as an error, not success. |

Error speech uses English or Portuguese based on `user_input.language` so both household languages
receive understandable messages. The agent's own reply text is passed through unchanged.

**Rationale**: This satisfies the constitution's requirement that the assistant never claims an
action succeeded when the underlying service did not confirm it. It also keeps the adapter free of
tool policy: the agent decides outcomes; Home Assistant only reports them.

**Alternatives considered**:

- Raising `HomeAssistantError`: HA converts it to a generic error, losing the agent's code and
  message. Returning an explicit error response gives better voice behavior.
- Treating an empty reply as success with an empty speech: rejected; it sounds broken and hides a
  failure.

## Decision: Keep confirmation state in memory per conversation with explicit lifecycle

**Decision**: Store a `PendingConfirmation` record keyed by conversation ID in the conversation
entity. Fields: `token`, `tool`, `arguments_preview`, `expires_at`, `language`, `created_at`.
When a follow-up arrives:

1. If the pending record is missing, process the text as a new `/conversation` request.
2. If expired locally, delete it and return an expiry message without calling `/confirm approve`.
3. Recognize affirmative and negative phrases in English and Portuguese.
4. For an affirmative or negative decision, delete the record before awaiting `POST /confirm` so a
   concurrent or repeated request cannot approve it twice.
5. For an ambiguous follow-up, return a short clarification prompt and retain the pending record
   until expiry or an explicit decision.

**Rationale**: The agent's token is single-use, bound to caller and conversation, and expires after
120 seconds. Clearing before the network call enforces at-most-once within Home Assistant. Keeping
state in memory avoids persisting short-lived secrets; a Home Assistant restart simply loses the
pending prompt, and the agent's token expires on its own.

**Alternatives considered**:

- Persist pending confirmations in a HA Store: rejected because it adds a secret-at-rest surface for
  data that lives only 120 seconds.
- Auto-approve based on a keyword in the agent's reply: rejected; it would put tool policy in Home
  Assistant.
- Route ambiguous text to `/conversation` while a confirmation is pending: rejected because it can
  confuse the agent's pending state and loses the decision opportunity.

## Decision: Test with pytest-homeassistant-custom-component and mocked HTTP

**Decision**: Add `pytest.ini`, `requirements_test.txt`, and tests under `tests/`. Use the
`hass`, `enable_custom_integrations`, `MockConfigEntry`, and mocked aiohttp client fixtures from
`pytest-homeassistant-custom-component`. Pin the test package to a release compatible with Home
Assistant 2026.10.2. Cover:

- Config flow success and invalid/unreachable/timeout/unauthorized errors.
- Completed conversation reply with the expected body and bearer header.
- Failed status, timeout, connection error, and malformed response.
- Conversation ID reuse across turns.
- Confirmation approve, reject, expiry, ambiguous follow-up, and replay prevention (P2).
- No live agent, network, or cluster requirement.

**Rationale**: This is the standard harness for custom components and provides Home Assistant
fixtures without duplicating core test infrastructure. Mocking the shared client session verifies
the adapter's HTTP contract without a cluster.

**Alternatives considered**:

- `respx` or `aioresponses`: workable, but the PHACC/HA client mock fixture is already aligned with
  `async_get_clientsession`.
- Live agent integration tests: rejected for unit CI; reserved for manual smoke tests in quickstart.

## Decision: Document token creation and rotation in the agent repository

**Decision**: Document the exact agent-side command
`pnpm token:generate -- --caller-id home-assistant --permissions read,write`, placing only the hash
map in the cluster `agent-auth` Secret, and pasting the plaintext token into the Home Assistant
integration config entry. Note that the previously shared token must be rotated out. Document that
the Assist conversation-agent selection is stored in `.storage` on the PVC, not tracked YAML.

**Rationale**: The agent validates SHA-256 hashes from `AGENT_AUTH_TOKENS`; the plaintext token is
only needed by the caller. Keeping the hash in the cluster Secret and the plaintext in the HA config
entry satisfies the repository's no-secrets-in-Git rule.

**Alternatives considered**:

- Put the token in `secrets.yaml` or an environment variable: rejected; the requirement explicitly
  places it in the config entry and the config entry is PVC-backed.
- Reuse the existing shared token: rejected by the rotation requirement.

## Decision: No Dockerfile or workflow change beyond tracked config

**Decision**: Rely on the existing `COPY config/ /config-seed/` and the publish workflow's
`config/**` trigger. Add a verification step to the quickstart that inspects the built image for
`/config-seed/custom_components/home_sweet_home_agent/manifest.json`, then rebuild and let Flux roll
out the new image.

**Rationale**: The component is tracked configuration. Copying the whole `config/` tree already
includes it and keeps the image build free of special cases.

**Alternatives considered**:

- Separate build step or Python package install: unnecessary and would split configuration from its
  integration.
- Changing `.dockerignore`: unnecessary because `config/custom_components` is not excluded.
