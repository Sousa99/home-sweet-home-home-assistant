"""The Home Sweet Home Agent integration."""

from __future__ import annotations

from dataclasses import dataclass

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_CONVERSATION_TIMEOUT,
    DEFAULT_HEALTH_TIMEOUT,
)

PLATFORMS = [Platform.CONVERSATION]


@dataclass(slots=True)
class AgentRuntimeData:
    """Runtime data for one Home Sweet Home Agent config entry."""

    base_url: str
    token: str
    session: aiohttp.ClientSession
    conversation_timeout: aiohttp.ClientTimeout
    health_timeout: aiohttp.ClientTimeout


type HomeSweetHomeAgentConfigEntry = ConfigEntry[AgentRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant, entry: HomeSweetHomeAgentConfigEntry
) -> bool:
    """Set up Home Sweet Home Agent from a config entry."""
    entry.runtime_data = AgentRuntimeData(
        base_url=entry.data[CONF_URL].rstrip("/"),
        token=entry.data[CONF_TOKEN],
        session=async_get_clientsession(hass),
        conversation_timeout=aiohttp.ClientTimeout(
            total=DEFAULT_CONVERSATION_TIMEOUT
        ),
        health_timeout=aiohttp.ClientTimeout(total=DEFAULT_HEALTH_TIMEOUT),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HomeSweetHomeAgentConfigEntry
) -> bool:
    """Unload a Home Sweet Home Agent config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
