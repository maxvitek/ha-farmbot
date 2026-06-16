"""Binary sensor platform for FarmBot."""

from __future__ import annotations

from typing import Any

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

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return connection diagnostic details."""
        last_saw_api = self.coordinator.data.get("last_saw_api")
        if last_saw_api is None:
            return None
        return {"last_saw_api": last_saw_api}


class FarmBotEstoppedBinarySensor(FarmBotEntity, BinarySensorEntity):
    """Whether the FarmBot is currently e-stopped."""

    _attr_unique_id = f"{DOMAIN}_estopped"
    _attr_name = "FarmBot E-Stopped"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        """Return true if e-stopped."""
        return bool(self.coordinator.data.get("estopped", False))
