"""Config flow for the Home Sweet Home Agent integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_TOKEN,
    CONF_URL,
    DEFAULT_HEALTH_TIMEOUT,
    DOMAIN,
    ERROR_CANNOT_CONNECT,
    ERROR_INVALID_AUTH,
    ERROR_TIMEOUT,
    ERROR_UNKNOWN,
    HEALTH_PATH,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
    }
)


def _normalize_url(value: str) -> str:
    """Normalize and validate the agent URL."""
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise vol.Invalid("invalid_url")
    return value


async def _async_validate_connection(
    hass: HomeAssistant, url: str, token: str
) -> str | None:
    """Validate the agent health endpoint."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            f"{url}{HEALTH_PATH}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=aiohttp.ClientTimeout(total=DEFAULT_HEALTH_TIMEOUT),
        ) as response:
            if response.status in (401, 403):
                return ERROR_INVALID_AUTH
            if response.status != 200:
                return ERROR_CANNOT_CONNECT
            return None
    except TimeoutError:
        return ERROR_TIMEOUT
    except aiohttp.ClientError:
        return ERROR_CANNOT_CONNECT
    except ValueError:
        return ERROR_CANNOT_CONNECT
    except Exception:
        _LOGGER.exception("Unexpected error validating the Home Sweet Home Agent")
        return ERROR_UNKNOWN


class HomeSweetHomeAgentConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Home Sweet Home Agent config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}

        data_schema = STEP_USER_DATA_SCHEMA

        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            data_schema = self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, {CONF_URL: user_input[CONF_URL]}
            )
            try:
                url = _normalize_url(user_input[CONF_URL])
            except vol.Invalid:
                errors["base"] = ERROR_CANNOT_CONNECT
            else:
                if not token:
                    errors["base"] = ERROR_INVALID_AUTH
                else:
                    error = await _async_validate_connection(
                        self.hass, url, token
                    )
                    if error is None:
                        await self.async_set_unique_id(url)
                        self._abort_if_unique_id_configured()
                        return self.async_create_entry(
                            title="Home Sweet Home Agent",
                            data={CONF_URL: url, CONF_TOKEN: token},
                        )
                    errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
