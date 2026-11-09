"""Shared fixtures for the Home Sweet Home Agent tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from custom_components.home_sweet_home_agent.const import CONF_TOKEN, CONF_URL, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

AGENT_URL = "http://agent.test:3400"
AGENT_TOKEN = "test-bearer-token"
CUSTOM_COMPONENTS = Path(__file__).resolve().parents[1] / "config" / "custom_components"


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Copy the repository custom components into the temporary HA config."""
    target = Path(hass_tmp_config_dir) / "custom_components"
    target.mkdir(exist_ok=True)
    shutil.copytree(CUSTOM_COMPONENTS, target, dirs_exist_ok=True)
    return hass_tmp_config_dir


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in every test."""
    yield


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant) -> None:
    """Set up the core homeassistant integration needed by conversation."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()


@pytest.fixture
def agent_url() -> str:
    """Return the test agent URL."""
    return AGENT_URL


@pytest.fixture
def agent_token() -> str:
    """Return the test bearer token."""
    return AGENT_TOKEN


@pytest.fixture
def mock_agent_entry(hass: HomeAssistant, agent_url: str, agent_token: str) -> MockConfigEntry:
    """Add an adapter config entry to Home Assistant without setting it up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home Sweet Home Agent",
        data={CONF_URL: agent_url, CONF_TOKEN: agent_token},
        unique_id=agent_url,
    )
    entry.add_to_hass(hass)
    return entry
