"""Shared entity classes for FarmBot."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN, MANUFACTURER, MODEL
from .coordinator import FarmBotDataUpdateCoordinator


class FarmBotEntity(CoordinatorEntity[FarmBotDataUpdateCoordinator]):
    """Base entity for FarmBot entities."""

    _attr_has_entity_name = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the FarmBot controller."""
        sw_version = self.coordinator.data.get("fbos_version")
        hw_version = self.coordinator.data.get("firmware_version")

        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=DEFAULT_NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
            sw_version=sw_version,
            hw_version=hw_version,
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Allow subclasses to add attributes."""
        return None
