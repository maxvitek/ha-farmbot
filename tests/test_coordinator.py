"""Tests for FarmBot coordinator."""

from __future__ import annotations

from unittest.mock import Mock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.farmbot.const import DOMAIN
from custom_components.farmbot.coordinator import FarmBotDataUpdateCoordinator


async def test_coordinator_fetches_and_parses(hass, farmbot_credentials, mock_farmbot):
    """Test coordinator update parsing."""
    entry = MockConfigEntry(domain=DOMAIN, data=farmbot_credentials)
    coordinator = FarmBotDataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    assert coordinator.data["position"] == {"x": 100.0, "y": 200.0, "z": -10.0}
    assert coordinator.data["connected"] is True
    assert coordinator.data["estopped"] is False
    assert len(coordinator.data["sequences"]) == 3
    assert coordinator.data["latest_image"]["attachment_url"] == "https://example.com/latest.jpg"
    assert coordinator.data["soil_readings"]["59"]["value"] == 330


async def test_coordinator_refreshes_token_on_auth_failure(hass, farmbot_credentials, mock_farmbot):
    """Test retry path for auth failures."""
    original_api_get = mock_farmbot.api_get

    def _side_effect(endpoint: str):
        if endpoint == "device" and _side_effect.calls == 0:
            _side_effect.calls += 1
            raise Exception("401 Unauthorized")
        return original_api_get(endpoint)

    _side_effect.calls = 0
    mock_farmbot.api_get = Mock(side_effect=_side_effect)

    entry = MockConfigEntry(domain=DOMAIN, data=farmbot_credentials)
    coordinator = FarmBotDataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    assert mock_farmbot.get_token.call_count >= 2
    assert coordinator.data["connected"] is True
