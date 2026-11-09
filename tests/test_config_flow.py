"""Config flow tests for the Home Sweet Home Agent integration."""

from __future__ import annotations

import aiohttp
import pytest
from custom_components.home_sweet_home_agent.const import CONF_TOKEN, CONF_URL, DOMAIN
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def _start_flow(hass: HomeAssistant) -> data_entry_flow.FlowResult:
    """Start the user config flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_config_flow_creates_entry(
    hass: HomeAssistant,
    aioclient_mock,
    agent_url: str,
    agent_token: str,
) -> None:
    """A healthy agent creates a config entry with a normalized URL."""
    aioclient_mock.get(f"{agent_url}/healthz", status=200)

    result = await _start_flow(hass)
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: f"{agent_url}/", CONF_TOKEN: f" {agent_token} "},
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home Sweet Home Agent"
    assert result["data"] == {CONF_URL: agent_url, CONF_TOKEN: agent_token}
    assert aioclient_mock.mock_calls[0][0] == "GET"
    assert str(aioclient_mock.mock_calls[0][1]) == f"{agent_url}/healthz"
    assert (
        aioclient_mock.mock_calls[0][3]["Authorization"] == f"Bearer {agent_token}"
    )

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == agent_url


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, "invalid_auth"),
        (403, "invalid_auth"),
        (500, "cannot_connect"),
    ],
)
async def test_config_flow_rejects_unsuccessful_health(
    hass: HomeAssistant,
    aioclient_mock,
    agent_url: str,
    agent_token: str,
    status: int,
    error: str,
) -> None:
    """Unauthorized or unexpected health responses keep the flow open."""
    aioclient_mock.get(f"{agent_url}/healthz", status=status)

    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: agent_url, CONF_TOKEN: agent_token}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_config_flow_timeout(
    hass: HomeAssistant,
    aioclient_mock,
    agent_url: str,
    agent_token: str,
) -> None:
    """A health request that times out is reported clearly."""
    aioclient_mock.get(f"{agent_url}/healthz", exc=TimeoutError())

    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: agent_url, CONF_TOKEN: agent_token}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "timeout"}


async def test_config_flow_connection_error(
    hass: HomeAssistant,
    aioclient_mock,
    agent_url: str,
    agent_token: str,
) -> None:
    """A connection failure is reported clearly."""
    aioclient_mock.get(
        f"{agent_url}/healthz", exc=aiohttp.ClientConnectionError()
    )

    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: agent_url, CONF_TOKEN: agent_token}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_rejects_duplicate_url(
    hass: HomeAssistant,
    aioclient_mock,
    agent_url: str,
    agent_token: str,
    mock_agent_entry: MockConfigEntry,
) -> None:
    """A second entry for the same URL is rejected."""
    aioclient_mock.get(f"{agent_url}/healthz", status=200)

    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: agent_url, CONF_TOKEN: agent_token}
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_config_flow_rejects_invalid_url(
    hass: HomeAssistant,
    agent_token: str,
) -> None:
    """A URL without an HTTP scheme is rejected before any request."""
    result = await _start_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: "agent.local:3400", CONF_TOKEN: agent_token}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
