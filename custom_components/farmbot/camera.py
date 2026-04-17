"""Camera platform for FarmBot."""

from __future__ import annotations

from aiohttp import ClientError

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .entity import FarmBotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FarmBot camera entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([FarmBotLatestImageCamera(coordinator)])


class FarmBotLatestImageCamera(FarmBotEntity, Camera):
    """Camera exposing the latest FarmBot image."""

    _attr_unique_id = f"{DOMAIN}_latest_image"
    _attr_name = "FarmBot Latest Image"

    def __init__(self, coordinator) -> None:
        """Initialize camera with both parent classes."""
        FarmBotEntity.__init__(self, coordinator)
        Camera.__init__(self)

    @property
    def is_on(self) -> bool:
        """Return true when a latest image URL is available."""
        return self._image_url is not None

    @property
    def _image_url(self) -> str | None:
        image = self.coordinator.data.get("latest_image")
        if not isinstance(image, dict):
            return None
        return image.get("attachment_url") or image.get("url")

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Return latest image bytes."""
        image_url = self._image_url
        if not image_url:
            return None

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(image_url) as response:
                if response.status >= 400:
                    return None
                return await response.read()
        except ClientError:
            return None
