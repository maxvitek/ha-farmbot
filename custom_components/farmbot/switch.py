"""Switch platform for FarmBot peripherals."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DATA_COORDINATOR, DOMAIN
from .entity import FarmBotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FarmBot switches."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities: list[SwitchEntity] = []

    for peripheral in coordinator.data.get("peripherals", []):
        entities.append(FarmBotPeripheralSwitch(coordinator, peripheral))

    async_add_entities(entities)


class FarmBotPeripheralSwitch(FarmBotEntity, SwitchEntity):
    """Switch entity representing a FarmBot peripheral pin."""

    def __init__(self, coordinator, peripheral: dict) -> None:
        super().__init__(coordinator)
        self._peripheral_id = str(peripheral["id"])
        self._pin_number = int(peripheral["pin_number"])
        self._label = str(peripheral.get("name", f"Peripheral {self._pin_number}"))

        self._attr_unique_id = f"{DOMAIN}_peripheral_{self._peripheral_id}"
        self._attr_name = f"FarmBot {self._label}"
        self.entity_id = f"switch.farmbot_{slugify(self._label)}"

    @property
    def is_on(self) -> bool:
        """Return true if peripheral pin value is on."""
        for peripheral in self.coordinator.data.get("peripherals", []):
            if str(peripheral["id"]) == self._peripheral_id:
                return int(peripheral.get("value", 0)) != 0
        return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn peripheral on."""
        await self.coordinator.async_set_peripheral(self._pin_number, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn peripheral off."""
        await self.coordinator.async_set_peripheral(self._pin_number, False)
        await self.coordinator.async_request_refresh()
