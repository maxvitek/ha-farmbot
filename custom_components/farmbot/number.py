"""Number platform for FarmBot target coordinates."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
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
    """Set up FarmBot coordinate numbers."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities(
        [
            FarmBotTargetCoordinateNumber(coordinator, "x"),
            FarmBotTargetCoordinateNumber(coordinator, "y"),
            FarmBotTargetCoordinateNumber(coordinator, "z"),
        ]
    )


class FarmBotTargetCoordinateNumber(FarmBotEntity, NumberEntity):
    """FarmBot target coordinate number for one axis."""

    _attr_native_min_value = -10000.0
    _attr_native_max_value = 10000.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "mm"

    def __init__(self, coordinator, axis: str) -> None:
        super().__init__(coordinator)
        self._axis = axis
        self._attr_unique_id = f"{DOMAIN}_target_{axis}"
        self._attr_name = f"FarmBot Target {axis.upper()}"

    @property
    def native_value(self) -> float:
        """Return target axis value."""
        target = self.coordinator.data.get("target_position", {})
        return float(target.get(self._axis, 0.0))

    async def async_set_native_value(self, value: float) -> None:
        """Set axis value and execute a move command with XYZ target."""
        target = dict(self.coordinator.data.get("target_position", {}))
        target.setdefault("x", 0.0)
        target.setdefault("y", 0.0)
        target.setdefault("z", 0.0)
        target[self._axis] = float(value)

        await self.coordinator.async_move_absolute(
            float(target["x"]),
            float(target["y"]),
            float(target["z"]),
        )
        await self.coordinator.async_request_refresh()
