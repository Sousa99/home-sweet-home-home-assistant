# Contract: Home Sweet Home Agent HTTP Interface (Consumed)

**Feature**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md)

This contract is owned by `home-sweet-home-agent`. The adapter consumes it and must not change it.
The agent is reachable only through the private in-cluster service.

**Base URL**: `http://agent.agent.svc.cluster.local:3400`

**Authorization**: Every request except `/healthz` and `/readyz` requires
`Authorization: Bearer <token>`. The agent checks the caller against SHA-256 hashes in
`AGENT_AUTH_TOKENS`. The Home Assistant caller is granted `read,write`, so destructive tools are not
advertised.

**Sensitive data rule**: The adapter never logs the bearer token or confirmation token.

## GET /healthz

Used by the config flow to check reachability and best-effort authorization.

**Request**:

```http
GET /healthz HTTP/1.1
Authorization: Bearer <token>
```

**Expected**: `200 OK` for a reachable agent. The contract marks the probe as unauthenticated, so a
200 does not prove the token is valid; the adapter also treats 401/403 as an authentication failure
when the agent enforces it on the probe.

**Adapter handling**:

| Result | Config flow |
| --- | --- |
| 200 | Accept the configuration. |
| 401 / 403 | `invalid_auth`. |
| Timeout after 10 seconds | `timeout`. |
| Connection error | `cannot_connect`. |
| Other status | `cannot_connect`. |

## POST /conversation

Sends one user turn and receives one agent outcome.

**Request**:

```http
POST /conversation HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "<ConversationInput.text>",
  "conversationId": "<ConversationInput.conversation_id or chat_log.conversation_id>"
}
```

`conversationId` is omitted only if neither Home Assistant source provides one. The same ID is sent
for every turn of the exchange and returned to Assist.

**Timeout**: 90 seconds total, accommodating the agent's 30-second model timeout plus tool
execution.

**Response variants**:

### Completed

```json
{"status": "completed", "reply": "string", "trace": []}
```

Adapter: return `reply` as normal speech. An empty or missing `reply` is a malformed response and
becomes an error.

### Confirmation Required (P2)

```json
{
  "status": "confirmation_required",
  "reply": "string",
  "confirmation": {
    "token": "string",
    "tool": "string",
    "argumentsPreview": {},
    "expiresAt": "ISO-8601 timestamp"
  },
  "trace": []
}
```

Adapter: store one pending confirmation for the conversation, delete any previous pending record,
and return `reply` as speech. Nothing is executed by Home Assistant.

### Failed

```json
{"status": "failed", "error": {"code": "string", "message": "string"}}
```

Adapter: return an error response whose speech includes the code and message. Never return a normal
response.

### HTTP and Transport Failures

| Condition | Adapter behavior |
| --- | --- |
| 401 / 403 | Spoken credential error; instruct the user to update the integration. |
| 5xx | Spoken agent-unavailable error. |
| Other non-2xx | Spoken unexpected-response error. |
| Timeout | Spoken timeout error; do not retry automatically. |
| Connection error | Spoken unreachable error; do not retry automatically. |
| Malformed JSON / unknown `status` | Spoken unexpected-response error. |

No failure may raise out of the conversation entity. All failures return an error
`IntentResponse`.

## POST /confirm

Resolves a pending confirmation. P2 scope.

**Request**:

```http
POST /confirm HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "conversationId": "<same conversation id>",
  "confirmationToken": "<confirmation.token>",
  "decision": "approve" | "reject"
}
```

**Timeout**: 90 seconds.

**Adapter preconditions**:

- A pending confirmation exists for the conversation.
- The pending record has not expired locally.
- The follow-up is an explicit affirmative or negative.
- The pending record is removed before the request is sent, so a concurrent or repeated follow-up
  cannot send a second decision.

**Responses**: The same completed/failed shapes as `/conversation`. `completed` is returned as
speech; `failed` is returned as an error. An unknown or already-used token is surfaced as an expiry
or already-resolved error, never as success.

## Error Codes Visible to the User

The adapter includes the agent's `error.code` in spoken errors and logs. It does not invent codes.
Representative codes expected from the agent include model timeout, tool failure, authorization
failure, and invalid request, but the adapter passes through whatever code the agent returns.
