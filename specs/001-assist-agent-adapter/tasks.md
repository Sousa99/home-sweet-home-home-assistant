# Tasks: Assist Conversation Adapter for the Home Sweet Home Agent

**Input**: Design documents from `/specs/001-assist-agent-adapter/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included because the feature specification explicitly requires mocked-HTTP tests for
completed, failed, timeout, connection error, invalid config, and confirmation flows.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated as
an independent increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story the task belongs to (US1, US2, US3)
- Every task includes an exact file path

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the tracked integration skeleton and the isolated test harness.

- [X] T001 Create the component and test directory structure, including `config/custom_components/__init__.py`, `config/custom_components/home_sweet_home_agent/`, `config/custom_components/home_sweet_home_agent/translations/`, and `tests/`
- [X] T002 [P] Create `config/custom_components/home_sweet_home_agent/manifest.json` with domain `home_sweet_home_agent`, version `0.1.0`, `config_flow: true`, `integration_type: service`, `iot_class: local_polling`, `dependencies: ["conversation"]`, and repository metadata
- [X] T003 [P] Create `config/custom_components/home_sweet_home_agent/const.py` with `DOMAIN`, `CONF_URL`, `CONF_TOKEN`, endpoint paths, 90-second conversation timeout, 10-second health timeout, response status constants, and error keys
- [X] T004 [P] Create `pytest.ini` and `requirements_test.txt` with `pytest-homeassistant-custom-component` pinned to a release compatible with Home Assistant 2026.10.2, plus `asyncio_mode = auto` and `testpaths = tests`
- [X] T005 [P] Create `tests/conftest.py` with the `enable_custom_integrations` fixture, a reusable `MockConfigEntry` factory for the adapter, and shared mock-response fixtures
- [X] T006 [P] Create baseline `config/custom_components/home_sweet_home_agent/strings.json` and `config/custom_components/home_sweet_home_agent/translations/en.json` with config-flow step labels, descriptions, and error keys `cannot_connect`, `invalid_auth`, and `timeout`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Wire the config entry and conversation platform. No network calls happen during setup.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T007 [P] Implement config-entry setup and unload in `config/custom_components/home_sweet_home_agent/__init__.py`, including a runtime data container for base URL, token, shared client session, and timeouts, and forwarding `Platform.CONVERSATION`
- [X] T008 Implement the conversation platform setup and entity skeleton in `config/custom_components/home_sweet_home_agent/conversation.py` with `supported_languages = MATCH_ALL`, `should_poll = False`, a stable unique ID, and the `_async_handle_message` entry point

**Checkpoint**: The integration loads from a config entry and exposes an Assist-selectable conversation entity.

---

## Phase 3: User Story 1 - Ask the Household Assistant a Question (Priority: P1) 🎯 MVP

**Goal**: Validate the agent URL/credential, forward text and conversation identifiers, return
completed replies as speech, and turn every failure into a clear spoken error.

**Independent Test**: Create a config entry against a mocked `/healthz`, select the agent, send a
mocked completed request, and verify the reply, bearer header, body, and conversation ID. Repeat for
failed, timeout, connection error, malformed, and 401 responses.

### Tests for User Story 1

- [X] T009 [P] [US1] Write config-flow tests for successful setup, `cannot_connect`, `invalid_auth`, `timeout`, and duplicate URL rejection in `tests/test_config_flow.py`
- [X] T010 [P] [US1] Write conversation tests for completed reply, conversation ID reuse across turns, bearer header and request body, agent `failed` status, empty reply, malformed response, HTTP 401/5xx, timeout, and connection error in `tests/test_conversation.py`

### Implementation for User Story 1

- [X] T011 [US1] Implement the config flow in `config/custom_components/home_sweet_home_agent/config_flow.py` with URL/token schema, URL normalization, unique ID, `GET /healthz` validation, and error mapping
- [X] T012 [US1] Implement `_async_handle_message` in `config/custom_components/home_sweet_home_agent/conversation.py` to derive and reuse the conversation ID, send `user_input.text`, add assistant content to the chat log, and return `ConversationResult`
- [X] T013 [US1] Implement the outbound `POST /conversation` request in `config/custom_components/home_sweet_home_agent/conversation.py` using `async_get_clientsession`, the bearer header, JSON body, and a 90-second timeout
- [X] T014 [US1] Implement outcome mapping in `config/custom_components/home_sweet_home_agent/conversation.py` for `completed`, `failed`, unknown statuses, 401/403, 5xx, timeout, connection errors, and invalid JSON, returning `IntentResponseResponseType.ERROR` speech on every failure
- [X] T015 [US1] Add English and Portuguese spoken error templates and an empty-input clarification in `config/custom_components/home_sweet_home_agent/conversation.py`, and ensure the token is never included in logs or exceptions
- [X] T016 [US1] Complete config-flow error keys and entry text in `config/custom_components/home_sweet_home_agent/strings.json` and `config/custom_components/home_sweet_home_agent/translations/en.json`
- [X] T017 [US1] Run `python -m pytest tests/test_config_flow.py tests/test_conversation.py` and fix all User Story 1 failures

**Checkpoint**: User Story 1 is independently functional: valid setup, grounded replies, and safe spoken failures.

---

## Phase 4: User Story 2 - Control Devices Through Assist (Priority: P2)

**Goal**: Expose device control capability through the agent, keep the adapter free of MCP/tool
state, and confirm read/write-only phase 1 behavior.

**Independent Test**: With a mocked completed device-control reply, ask Assist to perform a
reversible action and verify the request is forwarded verbatim, the reply is spoken, the entity
advertises `CONTROL`, and no MCP or module traffic originates from Home Assistant.

### Tests for User Story 2

- [X] T018 [P] [US2] Write device-control tests in `tests/test_write_control.py` covering a completed write-class reply, exact text forwarding, `CONTROL` feature advertisement, and absence of any additional outbound requests or MCP imports

### Implementation for User Story 2

- [X] T019 [US2] Add `ConversationEntityFeature.CONTROL` to the entity in `config/custom_components/home_sweet_home_agent/conversation.py` and verify `manifest.json` declares no MCP or tool client dependency
- [X] T020 [US2] Run `python -m pytest tests/test_write_control.py` and fix all User Story 2 failures

**Checkpoint**: User Stories 1 and 2 work independently: questions and reversible device actions both flow through the agent only.

---

## Phase 5: User Story 3 - Confirm a Consequential Action (Priority: P3)

**Goal**: Support `confirmation_required` by retaining a pending token per conversation and
resolving a yes/no follow-up through `POST /confirm` with expiry and single-use enforcement.

**Independent Test**: Trigger a mocked `confirmation_required`, approve it once, and verify exactly
one `/confirm` call. Repeat for rejection, ambiguous follow-up, local expiry, and replay after
resolution.

### Tests for User Story 3

- [X] T021 [P] [US3] Write confirmation tests for approve, reject, ambiguous follow-up, local expiry, expired agent token, and replay prevention in `tests/test_confirmation.py`

### Implementation for User Story 3

- [X] T022 [US3] Add the `PendingConfirmation` data structure and per-conversation pending storage with cleanup in `config/custom_components/home_sweet_home_agent/conversation.py`
- [X] T023 [US3] Handle `status: confirmation_required` in `config/custom_components/home_sweet_home_agent/conversation.py` by storing token, tool, argument preview, expiry, and language, and returning the agent reply as speech
- [X] T024 [US3] Implement explicit English and Portuguese affirmative/negative recognition plus ambiguous follow-up clarification in `config/custom_components/home_sweet_home_agent/conversation.py`
- [X] T025 [US3] Implement `POST /confirm` in `config/custom_components/home_sweet_home_agent/conversation.py`, deleting the pending record before awaiting the call, sending `approve` or `reject`, and refusing local-expired approvals without an approve call
- [X] T026 [US3] Add confirmation, cancellation, expiry, and already-resolved spoken templates for English and Portuguese in `config/custom_components/home_sweet_home_agent/conversation.py`
- [X] T027 [US3] Run `python -m pytest tests/test_confirmation.py` and fix all User Story 3 failures

**Checkpoint**: All user stories are independently functional, and an approval executes exactly once.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, image/rollout guidance, secret hygiene, and full validation.

- [X] T028 [P] Update `README.md` with the adapter overview, architecture flow, dedicated caller token summary, Assist pipeline selection, and image rebuild plus Flux rollout path
- [X] T029 [P] Update `docs/README.md` with `pnpm token:generate -- --caller-id home-assistant --permissions read,write`, hash-only storage in the cluster `agent-auth` Secret, rotation of the previously shared token, plaintext token placement in the config entry, `.storage` pipeline selection, 120-second voice confirmation TTL, and recovery steps
- [X] T030 [P] Create `tests/test_translations.py` to assert `strings.json` and `translations/en.json` expose the same config-flow keys
- [X] T031 Verify the published-image path by building the image and checking `/config-seed/custom_components/home_sweet_home_agent/manifest.json` and `conversation.py` in `Dockerfile`, then record the Flux rollout expectation in `quickstart.md`
- [X] T032 Run `python -m pytest` for the full suite and fix cross-story regressions in `tests/`
- [X] T033 Run a secret-hygiene review of `config/custom_components/home_sweet_home_agent/`, `tests/`, `README.md`, and `docs/README.md`; confirm no plaintext token, token logging, or tracked credential is present
- [ ] T034 Execute the validation scenarios in `quickstart.md` on the target Home Assistant instance, including read, write, confirmation, timeout, unavailable-agent, and token-rotation smoke tests, and record any environment-specific steps there

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Starts immediately; T001 must precede the other setup tasks, which may then run in parallel.
- **Foundational (Phase 2)**: Depends on Setup and blocks every user story.
- **User Story 1 (Phase 3)**: Depends on Foundational. This is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational and reuses the User Story 1 request path; its own test is independently runnable.
- **User Story 3 (Phase 5)**: Depends on User Story 1 for the HTTP path and can proceed independently of User Story 2.
- **Polish (Phase 6)**: Depends on the desired stories being complete.

### Within Each User Story

- Tests are written first and must fail before implementation.
- Config flow and request transport precede outcome and error mapping.
- Warning, confirmation, and expiry behavior precede the final story test run.
- Each story checkpoint is a valid stopping point.

### Parallel Opportunities

- Setup: T002, T003, T004, T005, and T006 target different files and can run together after T001.
- Foundational: T007 can start before T008, but T008 depends on the runtime data shape from T007.
- User Story 1: T009 and T010 are separate test files and can run in parallel.
- User Story 3: T021 can be authored in parallel with the User Story 3 implementation tasks while its tests are expected to fail.
- Polish: T028, T029, and T030 target different files and can run in parallel.

---

## Parallel Example: User Story 1

```bash
# Author both story test files together:
Task: "Write config-flow tests in tests/test_config_flow.py"
Task: "Write conversation tests in tests/test_conversation.py"
```

## Parallel Example: Polish

```bash
# Documentation and translation checks touch different files:
Task: "Update README.md with adapter and rollout overview"
Task: "Update docs/README.md with token lifecycle and pipeline guidance"
Task: "Create tests/test_translations.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1.
4. Stop and validate with `python -m pytest tests/test_config_flow.py tests/test_conversation.py`.
5. Deploy the adapter and verify a real Assist text request and an unavailable-agent response.

### Incremental Delivery

1. Deliver User Story 1: setup validation, grounded replies, and safe failures.
2. Deliver User Story 2: device control through the agent with `CONTROL` and no MCP client.
3. Deliver User Story 3: confirmation with single-use, rejection, and expiry handling.
4. Complete documentation, image verification, secret hygiene, and real-instance smoke tests.

### Notes

- The adapter must remain an HTTP relay. Do not add MCP sessions, LLM calls, prompts, or tool policy.
- The token belongs only in the config entry. Do not add it to YAML, tests, logs, or the image.
- `[P]` tasks touch different files and have no dependency on incomplete tasks.
- The live cluster smoke tests in T034 require the agent and Home Assistant deployment; all earlier tests are fully mocked.
