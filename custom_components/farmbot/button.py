"""Button platform for FarmBot."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DATA_COORDINATOR, DOMAIN
from .entity import FarmBotEntity

RESERVED_SEQUENCE_SLUGS = {"find_home"}


def _sequence_icon(name: str) -> str:
    """Select icon by sequence name keywords."""
    lowered = name.lower()
    if "water" in lowered:
        return "mdi:watering-can"
    if "home" in lowered:
        return "mdi:home-search"
    if "weed" in lowered:
        return "mdi:sprout-outline"
    if "photo" in lowered or "camera" in lowered:
        return "mdi:camera"
    return "mdi:play-circle"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FarmBot buttons."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[ButtonEntity] = [
        FarmBotActionButton(
            coordinator,
            unique_id=f"{DOMAIN}_cmd_e_stop",
            name="E-Stop",
            icon="mdi:alert-octagon",
            action=coordinator.async_emergency_lock,
        ),
        FarmBotActionButton(
            coordinator,
            unique_id=f"{DOMAIN}_cmd_unlock",
            name="Unlock",
            icon="mdi:lock-open-variant",
            action=coordinator.async_emergency_unlock,
        ),
        FarmBotActionButton(
            coordinator,
            unique_id=f"{DOMAIN}_cmd_take_photo",
            name="Take Photo",
            icon="mdi:camera",
            action=coordinator.async_take_photo,
        ),
        FarmBotFindHomeButton(coordinator),
    ]

    for sequence in coordinator.data.get("sequences", []):
        sequence_name = sequence.get("name")
        if not sequence_name:
            continue

        sequence_slug = slugify(sequence_name)
        if sequence_slug in RESERVED_SEQUENCE_SLUGS:
            continue

        entities.append(FarmBotSequenceButton(coordinator, sequence_name))

    async_add_entities(entities)


class FarmBotActionButton(FarmBotEntity, ButtonEntity):
    """FarmBot action button."""

    def __init__(
        self,
        coordinator,
        *,
        unique_id: str,
        name: str,
        icon: str,
        action: Callable[[], Any],
    ) -> None:
        super().__init__(coordinator)
        self._action = action
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_icon = icon

    async def async_press(self) -> None:
        """Press action button."""
        await self._action()
        await self.coordinator.async_request_refresh()


class FarmBotFindHomeButton(FarmBotEntity, ButtonEntity):
    """Dedicated Find Home button with backward-compatible entity_id."""

    _attr_unique_id = f"{DOMAIN}_run_find_home"
    _attr_name = "Run Find Home"
    _attr_icon = "mdi:home-search"
    entity_id = "button.run_find_home"

    async def async_press(self) -> None:
        """Run Find Home sequence if present, fallback to move command."""
        sequence = self.coordinator.data.get("sequences_by_slug", {}).get("find_home")
        if sequence and (sequence_name := sequence.get("name")):
            await self.coordinator.async_execute_sequence(sequence_name)
        else:
            await self.coordinator.async_move_absolute(0.0, 0.0, 0.0)
        await self.coordinator.async_request_refresh()


class FarmBotSequenceButton(FarmBotEntity, ButtonEntity):
    """Button for executing a FarmBot sequence."""

    def __init__(self, coordinator, sequence_name: str) -> None:
        super().__init__(coordinator)
        self._sequence_name = sequence_name
        sequence_slug = slugify(sequence_name)

        self._attr_unique_id = f"{DOMAIN}_run_{sequence_slug}"
        self._attr_name = f"Run {sequence_name}"
        self._attr_icon = _sequence_icon(sequence_name)

        if sequence_slug in {"water_everything", "find_home"}:
            self.entity_id = f"button.run_{sequence_slug}"

    async def async_press(self) -> None:
        """Execute sequence when button is pressed."""
        await self.coordinator.async_execute_sequence(self._sequence_name)
        await self.coordinator.async_request_refresh()
