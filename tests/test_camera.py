"""Camera tests for FarmBot."""

from __future__ import annotations

from homeassistant.helpers import entity_registry as er

from .common import setup_integration


async def test_camera_entity_loads(hass, farmbot_credentials, mock_farmbot, aioclient_mock):
    """Test latest image camera entity is created."""
    aioclient_mock.get("https://example.com/latest.jpg", content=b"jpgbytes", status=200)

    await setup_integration(hass, farmbot_credentials)

    registry = er.async_get(hass)
    entry = registry.async_get("camera.farmbot_latest_image")
    assert entry is not None
