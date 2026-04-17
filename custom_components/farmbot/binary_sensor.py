"""Binary sensor platform for FarmBot."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .entity import FarmBotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FarmBot binary sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        [
            FarmBotConnectedBinarySensor(coordinator),
            FarmBotEstoppedBinarySensor(coordinator),
        ]
    )


class FarmBotConnectedBinarySensor(FarmBotEntity, BinarySensorEntity):
    """Whether the FarmBot is online."""

    _attr_unique_id = f"{DOMAIN}_connected"
    _attr_name = "FarmBot Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return true if connected."""
        return bool(self.coordinator.data.get("connected", False))


class FarmBotEstoppedBinarySensor(FarmBotEntity, BinarySensorEntity):
    """Whether the FarmBot is currently e-stopped."""

    _attr_unique_id = f"{DOMAIN}_estopped"
    _attr_name = "FarmBot E-Stopped"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        """Return true if e-stopped."""
        return bool(self.coordinator.data.get("estopped", False))
