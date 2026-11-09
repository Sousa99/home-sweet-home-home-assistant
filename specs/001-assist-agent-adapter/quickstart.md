# Quickstart Validation: Assist Conversation Adapter

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

This guide proves the adapter works end to end. Unit tests need no live agent or cluster. The
deployment smoke tests use the real Home Assistant instance and the private in-cluster agent.

## 1. Create the dedicated caller token (agent repository)

Run this in the `home-sweet-home-agent` repository, not this one:

```bash
pnpm token:generate -- --caller-id home-assistant --permissions read,write
```

Store only the SHA-256 hash map entry in the cluster `agent-auth` Secret, for example under
`AGENT_AUTH_TOKENS`. Never commit the plaintext token. Keep the plaintext value for step 3 only.

Rotate the previously shared token at the same time. It must not remain valid after the dedicated
Home Assistant caller is in use.

## 2. Deploy the updated agent secret

Apply the rotated `agent-auth` Secret through the cluster's normal GitOps path, then confirm the
agent pod has restarted with the new environment or mounted secret. Verify:

```bash
kubectl -n agent get pods
kubectl -n agent rollout status deployment/agent
```

No agent code or contract changes are part of this feature.

## 3. Build and publish the Home Assistant image

The component is tracked under `config/custom_components/home_sweet_home_agent/`, and the Dockerfile
already copies `config/` to `/config-seed/`. Verify locally:

```bash
docker build -t home-assistant-config:local .
docker run --rm home-assistant-config:local \
  test -f /config-seed/custom_components/home_sweet_home_agent/manifest.json
docker run --rm home-assistant-config:local \
  test -f /config-seed/custom_components/home_sweet_home_agent/conversation.py
```

The publish workflow triggers on `config/**`. After it publishes, let Flux reconcile the cluster
image reference and roll out the Home Assistant deployment. The pod must restart so the image seed
refreshes `/config`. The PVC keeps `.storage`, databases, and the existing config entry.

```bash
kubectl -n home-assistant rollout status deployment/home-assistant
```

## 4. Create the integration config entry

1. Open Home Assistant.
2. Go to **Settings → Devices & services → Add integration**.
3. Select **Home Sweet Home Agent**.
4. Enter:
   - **Agent URL**: `http://agent.agent.svc.cluster.local:3400`
   - **Bearer token**: the plaintext token from step 1
5. Submit.

**Expected**:

- A reachable, authorized agent completes setup and creates a conversation entity.
- An unreachable URL shows `cannot_connect`.
- A 401/403 shows `invalid_auth`.
- A slow health check shows `timeout`.

The token is stored only in the config entry in `.storage` on the PVC. It is not written to tracked
YAML and must not appear in Home Assistant logs. Because the agent marks `/healthz` as
unauthenticated, a successful setup proves reachability and best-effort credential acceptance; a
revoked token is reported clearly on the first conversation request.

## 5. Select the conversation agent for Assist

1. Go to **Settings → Voice assistants**.
2. Choose the default Assist pipeline.
3. Set **Conversation agent** to **Home Sweet Home Agent**.
4. Save.

This selection is stored in `.storage` on the PVC, not in tracked YAML. Document it in the
deployment runbook and include it in backups.

## 6. Run the automated tests

Home Assistant 2026.10.2 requires Python 3.14. Create a virtual environment and install the test
requirements pinned for that Home Assistant release:

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements_test.txt
.venv/bin/python -m pytest
```

The test requirements pin `pytest-homeassistant-custom-component==0.13.373`, which resolves Home
Assistant 2026.10.2, plus the conversation integration requirements (`gazetteer-matcher`, `hassil`,
and `home-assistant-intents`) that the test harness does not install automatically.

**Expected**: all tests pass with no network access. Covered cases:

- Config flow success and `cannot_connect`, `invalid_auth`, and `timeout` errors.
- Completed reply and conversation ID reuse.
- Agent `failed` status surfaced as an error with the agent's code.
- Timeout, connection error, malformed response, and HTTP 401 paths.
- Confirmation approve, reject, expiry, ambiguous follow-up, and replay prevention (P2).
- Bearer header and request body shape.

## 7. Smoke-test on the real instance

Use Assist from a phone or the Home Assistant chat, then test with a voice satellite.

### Read request (P1)

Say or type a question that requires household grounding.

**Expected**: The agent's reply is spoken and the conversation continues when a follow-up is asked.
Home Assistant makes no module/MCP connection itself.

### Write request (P2)

Ask for a reversible device action, such as turning on a light.

**Expected**: The device changes and the reply confirms the result. The Home Assistant caller token
has `read,write`; destructive tools are not offered.

### Confirmation request (P2)

Ask for an action that the agent flags as requiring confirmation.

**Expected**:

- The assistant states the proposed action.
- Answering "yes" executes the action exactly once.
- Answering "no" executes nothing and confirms cancellation.
- Waiting longer than 120 seconds and then answering "yes" refuses the action and asks the user to
  repeat the request.
- Repeating "yes" after a completed approval does not execute a second action.

**Voice constraint**: Confirmation tokens expire after `CONFIRMATION_TTL_MS` (currently 120
seconds). Voice users must answer promptly; there is no automatic retry.

### Failure paths

1. Stop or scale down the agent, then make an Assist request.
   **Expected**: Clear "cannot reach the assistant" speech; no hang, no success claim.
2. Restore the agent and make another request.
   **Expected**: The pipeline recovers without reconfiguring the integration.
3. Temporarily configure a revoked token and make a request.
   **Expected**: A clear credential error instructing the user to update the integration.
4. Simulate a long model/tool run.
   **Expected**: The request either completes within 90 seconds or returns a timeout response; the
   Assist pipeline remains usable.

## 8. Verify secret hygiene

```bash
git grep -n -- '<paste-token-prefix>' || true
```

Also inspect Home Assistant logs and confirm the token is absent. The config entry is the only
storage location.

## 9. Recovery notes

- Back up `.storage` so the config entry and Assist pipeline selection survive a PVC restore.
- If the token is rotated, update the integration config entry; there is no YAML change.
- If the component does not appear after deployment, confirm the pod restarted and
  `/config/custom_components/home_sweet_home_agent/manifest.json` exists.
- If Assist uses a different conversation agent, re-select **Home Sweet Home Agent** in the pipeline.
