"""Config flow for FarmBot."""

from __future__ import annotations

from typing import Any

import farmbot
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SERVER, DEFAULT_SERVER, DOMAIN


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate user input allows us to connect."""
    token = await hass.async_add_executor_job(
        farmbot.get_token,
        data[CONF_EMAIL],
        data[CONF_PASSWORD],
        data[CONF_SERVER],
    )
    await hass.async_add_executor_job(farmbot.set_token, token)
    await hass.async_add_executor_job(farmbot.api_get, "device")
    return {"title": "FarmBot"}


class FarmBotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FarmBot."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_SERVER] = user_input[CONF_SERVER].strip().rstrip("/")

            unique_id = f"{user_input[CONF_EMAIL].lower()}@{user_input[CONF_SERVER].lower()}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                info = await _validate_input(self.hass, user_input)
            except Exception as err:  # broad catch to map sync lib errors to flow errors
                message = str(err).lower()
                if any(term in message for term in ("401", "403", "unauthorized", "forbidden")):
                    errors["base"] = "invalid_auth"
                elif any(term in message for term in ("timeout", "connect", "network")):
                    errors["base"] = "cannot_connect"
                else:
                    errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_SERVER, default=DEFAULT_SERVER): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
