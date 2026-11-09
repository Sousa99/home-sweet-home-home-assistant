# Contract: Home Assistant Conversation Entity

**Feature**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)

This is the interface the integration exposes to Home Assistant Assist. It is implemented with
`homeassistant.components.conversation.ConversationEntity` and registered by a conversation
platform.

## Entity registration

| Item | Value |
| --- | --- |
| Domain | `home_sweet_home_agent` |
| Platform | `conversation` |
| Entity name | `Home Sweet Home Agent` |
| Unique ID | Config entry ID |
| `supported_languages` | `MATCH_ALL` (`"*"`) |
| `supported_features` | `ConversationEntityFeature.CONTROL` |
| `should_poll` | `False` |

The entity is created only when a config entry exists. Setup does not contact the agent, so Home
Assistant can start while the agent is temporarily unavailable.

## Incoming request

`_async_handle_message(user_input: ConversationInput, chat_log: ChatLog)` receives:

| Field | Use |
| --- | --- |
| `user_input.text` | Sent as `message` to `/conversation`. |
| `user_input.conversation_id` | Primary conversation identifier; fallback is `chat_log.conversation_id`. |
| `user_input.language` | Chooses English or Portuguese error/confirmation wording. |
| `user_input.agent_id` | Used when adding assistant content to the chat log. |
| `chat_log` | Adds assistant content and supplies the fallback conversation ID. |

## Outgoing result

`ConversationResult` contains:

| Field | Behavior |
| --- | --- |
| `response` | `IntentResponse` with normal speech, or an error response with user-facing speech. |
| `conversation_id` | The same effective conversation ID sent to the agent. |
| `continue_conversation` | `False` for phase 1; P2 may set `True` when a confirmation is pending. |

All error paths use `IntentResponseResponseType.ERROR`. The adapter never raises an unhandled
exception from `_async_handle_message`, so a failed request cannot break the Assist pipeline.

## Phase 1 behavior

- Normal text: forward to `/conversation`, return `reply`.
- Agent failure: return error speech containing the agent's code and message.
- Timeout/connection/HTTP/malformed failure: return clear error speech.
- Device control: performed entirely by the agent; Home Assistant holds no MCP client or tool
  session.
- Destructive tools: not advertised because the caller token has `read,write` only.

## Phase 2 behavior

- `confirmation_required`: store the pending confirmation for the conversation and return the
  agent's reply. Set `continue_conversation` so Assist keeps listening where supported.
- Follow-up affirmative in English or Portuguese: delete the pending record, call `/confirm` with
  `decision: "approve"`, and return the outcome.
- Follow-up negative: delete the pending record, call `/confirm` with `decision: "reject"`, and
  return the cancellation outcome.
- Expired pending record: delete it, do not call approve, and return an expiry message.
- Ambiguous follow-up: keep the pending record and ask the user to answer yes or no.
- Replayed decision: no pending record exists, so no second action can be approved.
