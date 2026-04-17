"""Tests for FarmBot coordinator."""

from __future__ import annotations

from .common import setup_integration


async def test_coordinator_fetches_and_parses(hass, farmbot_credentials, mock_farmbot):
    """Test coordinator update parsing."""
    entry = await setup_integration(hass, farmbot_credentials)
    coordinator = hass.data["farmbot"][entry.entry_id]["coordinator"]

    assert coordinator.data["position"] == {"x": 100.0, "y": 200.0, "z": -10.0}
    assert coordinator.data["connected"] is True
    assert coordinator.data["estopped"] is False
    assert len(coordinator.data["sequences"]) == 3
    assert coordinator.data["latest_image"]["attachment_url"] == "https://example.com/latest.jpg"
    assert coordinator.data["soil_readings"]["59"]["value"] == 330


async def test_coordinator_refreshes_token_on_auth_failure(hass, farmbot_credentials, mock_farmbot):
    """Test retry path for auth failures."""
    original_side_effect = mock_farmbot.api_get.side_effect
    call_count = {"n": 0}

    def _side_effect(endpoint: str):
        if endpoint == "device" and call_count["n"] == 0:
            call_count["n"] += 1
            raise Exception("401 Unauthorized")
        return original_side_effect(endpoint)

    mock_farmbot.api_get.side_effect = _side_effect

    entry = await setup_integration(hass, farmbot_credentials)
    coordinator = hass.data["farmbot"][entry.entry_id]["coordinator"]

    assert mock_farmbot.get_token.call_count >= 2
    assert coordinator.data["connected"] is True
