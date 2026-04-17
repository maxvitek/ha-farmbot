"""Tests for FarmBot config flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType

from custom_components.farmbot.const import CONF_SERVER, DEFAULT_SERVER, DOMAIN


async def test_config_flow_success(hass, mock_farmbot):
    """Test successful config flow."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] == FlowResultType.FORM

    user_input = {
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "secret",
        CONF_SERVER: DEFAULT_SERVER,
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=user_input)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "FarmBot"
    assert result["data"][CONF_EMAIL] == "user@example.com"
    mock_farmbot.get_token.assert_called()  # called in config flow + coordinator first refresh
    mock_farmbot.api_get.assert_any_call("device")


async def test_config_flow_invalid_auth(hass, mock_farmbot):
    """Test invalid auth mapping."""
    mock_farmbot.get_token.side_effect = Exception("401 Unauthorized")

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EMAIL: "user@example.com",
            CONF_PASSWORD: "bad",
            CONF_SERVER: DEFAULT_SERVER,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
