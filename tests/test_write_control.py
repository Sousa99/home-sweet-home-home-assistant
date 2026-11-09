"""Device-control tests for the Home Sweet Home Agent integration."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.home_sweet_home_agent.const import DOMAIN
from homeassistant.components import conversation
from homeassistant.components.conversation import ConversationEntityFeature
from homeassistant.core import Context, HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "custom_components"
    / "home_sweet_home_agent"
    / "manifest.json"
)


async def test_write_class_action_is_relayed_without_mcp(
    hass: HomeAssistant,
    aioclient_mock,
    mock_agent_entry: MockConfigEntry,
    agent_url: str,
) -> None:
    """A write-class action is performed by the agent, not Home Assistant."""
    assert await hass.config_entries.async_setup(mock_agent_entry.entry_id)
    await hass.async_block_till_done()

    agent = conversation.async_get_agent(hass, mock_agent_entry.entry_id)
    assert agent is not None
    assert agent.supported_features & ConversationEntityFeature.CONTROL

    aioclient_mock.post(
        f"{agent_url}/conversation",
        json={
            "status": "completed",
            "reply": "I turned on the living room light.",
        },
    )

    result = await conversation.async_converse(
        hass,
        "Turn on the living room light",
        None,
        Context(),
        language="en",
        agent_id=mock_agent_entry.entry_id,
    )

    assert result.response.response_type.name == "ACTION_DONE"
    assert result.response.speech["plain"]["speech"] == (
        "I turned on the living room light."
    )
    assert aioclient_mock.call_count == 1
    method, url, data, _headers = aioclient_mock.mock_calls[0]
    assert method == "POST"
    assert str(url) == f"{agent_url}/conversation"
    assert data["message"] == "Turn on the living room light"


def test_manifest_has_no_tool_client_dependency() -> None:
    """The integration remains a thin HTTP adapter."""
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["domain"] == DOMAIN
    assert manifest["dependencies"] == ["conversation"]
    assert "requirements" not in manifest
