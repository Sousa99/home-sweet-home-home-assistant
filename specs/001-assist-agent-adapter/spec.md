# Feature Specification: Assist Conversation Adapter for the Home Sweet Home Agent

**Feature Branch**: `feature/001-assist-agent-adapter`

**Created**: 2026-11-07

**Status**: Draft

**Input**: User description: "Add a Home Assistant conversation adapter so Assist (text and voice) can talk to the Home Sweet Home agent, which is already running in the cluster."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Ask the Household Assistant a Question (Priority: P1)

A household member configures Home Assistant to use the Home Sweet Home agent as its conversation
agent, then asks a question in Portuguese or English through Assist on their phone or a home voice
device. The assistant returns the agent's grounded answer as spoken reply text. If the agent cannot
answer, the member hears a clear error instead of a fabricated success.

**Why this priority**: This is the minimum viable integration. Without a validated connection and
reliable question-answering, no other capability matters. It also establishes the secure credential
handling and failure behavior that all later flows depend on.

**Independent Test**: Configure the adapter with a valid agent endpoint and credential, select it
as the Assist conversation agent, and send a text request. Verify that the agent's reply is returned
as the spoken response and that the conversation identifier is retained across turns. Repeat with a
voice request through the same pipeline.

**Acceptance Scenarios**:

1. **Given** a valid agent endpoint and caller credential, **When** the household member completes
   setup, **Then** setup succeeds and the adapter is available as a conversation agent.
2. **Given** an unreachable agent endpoint, **When** the member attempts setup, **Then** setup is
   rejected with an understandable explanation.
3. **Given** an invalid or unauthorized caller credential, **When** the member attempts setup,
   **Then** setup is rejected with an understandable authorization explanation.
4. **Given** a healthy agent and an active conversation, **When** the member asks a question,
   **Then** the agent's reply is returned as the spoken answer.
5. **Given** an active conversation, **When** the member asks a follow-up, **Then** the same
   conversation is continued rather than starting a new one.
6. **Given** the agent reports a failed request, **When** the member is listening, **Then** they
   hear an error that references the agent's failure reason and no success is claimed.
7. **Given** the agent is unreachable or exceeds the allowed response time, **When** the member
   makes a request, **Then** they hear a clear unavailable/timeout response and the Assist pipeline
   remains usable.
8. **Given** a request in Portuguese or English, **When** it is processed, **Then** the reply is
   returned without requiring the member to change language settings.

---

### User Story 2 - Control Devices Through Assist (Priority: P2)

A household member asks Assist to perform a routine device action, such as turning on a light or
adjusting a thermostat. The agent performs the action through its own authorized tooling and returns
a confirmation. Home Assistant only relays the conversation; it does not maintain its own tool
session.

**Why this priority**: Device control is the main practical value beyond question-answering, but it
depends on the validated conversation path from User Story 1. It must be delivered with only
read/write permissions so that consequential actions remain outside the phase 1 surface.

**Independent Test**: With a valid configuration and an agent caller limited to read and write
permissions, ask Assist to perform a reversible device action. Verify that the device state changes
and that the spoken reply confirms the result without Home Assistant holding any tool client.

**Acceptance Scenarios**:

1. **Given** a healthy agent with read/write permissions, **When** the member requests a reversible
   device action, **Then** the action is performed and the result is returned as speech.
2. **Given** phase 1 permissions, **When** the agent evaluates available tools, **Then** destructive
   tools are not offered through the Home Assistant connection.
3. **Given** a device action that the agent cannot complete, **When** the member is listening,
   **Then** they hear an error and the system does not claim the device changed.

---

### User Story 3 - Confirm a Consequential Action (Priority: P3)

A household member requests an action that the agent requires confirmation for. The assistant
announces what is about to happen and waits for a yes/no follow-up. The member approves or declines,
and exactly one action is performed or skipped. If the confirmation expires, the assistant explains
that the request must be repeated.

**Why this priority**: Confirmation is required for safety with consequential actions, but the core
read and write experience must exist first. Text users can rely on the full confirmation window;
voice users must respond within the short confirmation lifetime.

**Independent Test**: Trigger a confirmation-required request, approve it, and verify exactly one
action occurs. Repeat with a decline and with an expired confirmation and verify no action occurs in
either case.

**Acceptance Scenarios**:

1. **Given** the agent requests confirmation, **When** the member is prompted, **Then** the prompt
   identifies the proposed action and its arguments clearly enough to decide.
2. **Given** a pending confirmation, **When** the member approves, **Then** the action executes
   exactly once.
3. **Given** a pending confirmation, **When** the member declines, **Then** no action executes and
   the member hears that the request was cancelled.
4. **Given** a pending confirmation, **When** the confirmation lifetime passes, **Then** approval is
   refused, no action executes, and the member hears that the request expired.
5. **Given** an already-used confirmation, **When** the member attempts to approve it again,
   **Then** no second action executes.

---

### Edge Cases

- The agent is temporarily unavailable in the middle of an ongoing conversation.
- The agent rejects the caller credential after it was previously valid, for example after rotation.
- The agent takes longer than the allowed response window because of model latency or tool work.
- The agent returns an unexpected or malformed response body.
- The member speaks a very long reply or uses a language other than Portuguese or English.
- The member sends an empty or whitespace-only request.
- A confirmation is approved after expiry, is approved twice, or arrives for a different
  conversation.
- Two household members have separate active conversations at the same time.
- The integration is updated in the image but the existing configuration entry survives on the PVC.
- The configuration entry exists but the Assist pipeline still points at a different conversation
  agent.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Users MUST be able to configure the adapter from the Home Assistant interface by
  supplying the agent endpoint and a caller credential.
- **FR-002**: The adapter MUST validate the endpoint and credential during setup and reject
  unreachable or unauthorized configurations with a clear, user-facing explanation.
- **FR-003**: The caller credential MUST be stored only in the Home Assistant configuration entry
  backed by persistent storage. It MUST NOT appear in tracked repository files, YAML configuration,
  or logs.
- **FR-004**: The adapter MUST register as a conversation agent that can be selected for the Assist
  pipeline.
- **FR-005**: The adapter MUST forward the member's request text and the current conversation
  identifier, and MUST reuse that conversation identifier for the whole exchange.
- **FR-006**: The adapter MUST return completed agent replies as the spoken response, preserving the
  reply text.
- **FR-007**: The adapter MUST surface agent-reported failures as spoken errors that include the
  agent's failure reason. It MUST NOT return a success response for a failed request.
- **FR-008**: The adapter MUST enforce a bounded response window that accommodates the agent's model
  timeout plus tool execution (at least 90 seconds), and MUST return a clear timeout response rather
  than hanging the pipeline.
- **FR-009**: The adapter MUST handle connection failures, timeouts, and malformed responses without
  crashing or blocking the Assist pipeline.
- **FR-010**: The adapter MUST support Portuguese and English requests without per-request language
  configuration.
- **FR-011**: The adapter MUST signal that the conversation agent can control devices.
- **FR-012**: Phase 1 MUST support read and write actions performed entirely by the agent. Home
  Assistant MUST NOT hold its own tool session or independently contact module services.
- **FR-013**: Phase 1 MUST NOT advertise destructive actions through the Home Assistant caller
  credential.
- **FR-014**: (P2) When the agent requests confirmation, the adapter MUST present the proposed
  action, retain the pending confirmation for that conversation, and accept a follow-up approval or
  rejection from the member.
- **FR-015**: (P2) An approved confirmation MUST execute exactly one action. A declined, expired, or
  already-used confirmation MUST execute no action and MUST produce a clear spoken explanation.
- **FR-016**: (P2) Confirmation handling MUST respect the agent's 120-second confirmation lifetime,
  and documentation MUST note that voice users have very little time to respond.
- **FR-017**: The integration MUST be included in the published Home Assistant image and MUST load
  after the tracked configuration seed has run.
- **FR-018**: Documentation MUST describe generating a dedicated Home Assistant caller credential
  with read and write permissions, storing only its hash in the cluster secret, placing the
  plaintext value in the configuration entry, and rotating the previously shared credential.
- **FR-019**: Documentation MUST describe selecting the adapter as the Assist conversation agent,
  note that the selection lives in persistent storage rather than tracked YAML, and describe the
  image rebuild and rollout path.
- **FR-020**: Automated tests MUST cover completed replies, agent failures, timeouts, connection
  errors, invalid configuration, and the phase 2 confirmation flows without requiring a live agent
  or cluster.

### Key Entities _(include if feature involves data)_

- **Adapter Configuration**: The agent endpoint and caller credential that connect Home Assistant to
  the agent. The credential is sensitive and persists across restarts.
- **Conversation Exchange**: A request/reply pair identified by a conversation identifier, shared by
  all turns in one Assist conversation.
- **Pending Confirmation**: A temporary record of an action awaiting approval, associated with one
  conversation, with a proposed action summary, a single-use token, and an expiry time.
- **Agent Reply**: A completed answer, a request for confirmation, or a failure with a reason.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: With a healthy agent, at least 95% of Assist text and voice requests over a representative
  sample return a spoken reply without manual retry.
- **SC-002**: 100% of tested unreachable, unauthorized, timeout, connection-error, and agent-failure
  cases produce a clear spoken error and leave the pipeline ready for the next request.
- **SC-003**: A household member can complete setup with a valid endpoint and credential in under
  two minutes, and invalid setups are rejected 100% of the time.
- **SC-004**: Reversible device-control requests complete end to end through Assist without Home
  Assistant maintaining any tool session of its own.
- **SC-005**: In confirmation testing, exactly one action executes per approval, and zero actions
  execute for declined, expired, or replayed confirmations.
- **SC-006**: Repository scans and log inspection find zero occurrences of the plaintext caller
  credential.
- **SC-007**: A clean deployment built from the published image exposes the adapter after
  configuration seeding, with no manual file copying.
- **SC-008**: Portuguese and English requests both succeed through the same configured agent.

## Assumptions

- The agent's private HTTP contract is stable and owned by the `home-sweet-home-agent` repository;
  this feature does not change the contract or runtime.
- A dedicated Home Assistant caller credential will be created with read and write permissions and
  a hash-only entry in the cluster's agent authentication secret.
- The 90-second wait bound is sufficient for the agent's 30-second model timeout plus tool
  execution; longer agent work is treated as a timeout from Home Assistant's perspective.
- The 120-second confirmation lifetime is acceptable for text users; voice users must respond
  quickly, and expiry produces a repeat-the-request message rather than an automatic retry.
- Home Assistant 2026.10.2 remains the supported runtime and its persistent volume preserves
  `.storage`, including the configuration entry and Assist pipeline selection.
- The adapter needs no public ingress; it reaches the agent through the private in-cluster service.
- Proactive notifications, announcement policy, text-to-speech behavior, and public agent exposure
  remain out of scope.
- The integration may be enabled by a configuration entry created through the UI; no tracked YAML
  entity configuration is required.
