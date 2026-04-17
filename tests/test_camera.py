"""Camera tests for FarmBot."""

from __future__ import annotations

from homeassistant.components.camera import async_get_image

from .common import setup_integration


async def test_camera_entity_loads(hass, farmbot_credentials, mock_farmbot, aioclient_mock):
    """Test latest image camera downloads bytes."""
    aioclient_mock.get("https://example.com/latest.jpg", body=b"jpgbytes", status=200)

    await setup_integration(hass, farmbot_credentials)

    state = hass.states.get("camera.farmbot_latest_image")
    assert state is not None

    image = await async_get_image(hass, "camera.farmbot_latest_image")
    assert image.content == b"jpgbytes"
