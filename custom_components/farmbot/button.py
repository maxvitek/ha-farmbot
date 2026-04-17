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


def _sequence_icon(name: str) -> str:
    """Select icon by sequence name keywords."""
    lowered = name.lower()
    if "water" in lowered:
        return "mdi:watering-can"
    if "weed" in lowered:
        return "mdi:sprout-outline"
    if "photo" in lowered or "camera" in lowered:
        return "mdi:camera"
    if "plant" in lowered or "seed" in lowered:
        return "mdi:seed"
    if "move" in lowered:
        return "mdi:axis-arrow"
    if "home" in lowered:
        return "mdi:home-search"
    if "calibrat" in lowered:
        return "mdi:tune"
    if "mount" in lowered or "tool" in lowered:
        return "mdi:hammer-wrench"
    return "mdi:play-circle"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FarmBot buttons."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    # Built-in action buttons (celery_script commands, always present)
    entities: list[ButtonEntity] = [
        FarmBotActionButton(
            coordinator,
            unique_id=f"{DOMAIN}_find_home",
            name="FarmBot Find Home",
            icon="mdi:home-search",
            action=coordinator.async_find_home,
        ),
        FarmBotActionButton(
            coordinator,
            unique_id=f"{DOMAIN}_e_stop",
            name="FarmBot E-Stop",
            icon="mdi:alert-octagon",
            action=coordinator.async_emergency_lock,
        ),
        FarmBotActionButton(
            coordinator,
            unique_id=f"{DOMAIN}_unlock",
            name="FarmBot Unlock",
            icon="mdi:lock-open-variant",
            action=coordinator.async_emergency_unlock,
        ),
        FarmBotActionButton(
            coordinator,
            unique_id=f"{DOMAIN}_take_photo",
            name="FarmBot Take Photo",
            icon="mdi:camera",
            action=coordinator.async_take_photo,
        ),
        FarmBotActionButton(
            coordinator,
            unique_id=f"{DOMAIN}_sync",
            name="FarmBot Sync",
            icon="mdi:sync",
            action=coordinator.async_sync,
        ),
    ]

    # Dynamic sequence buttons (one per user-defined sequence)
    for sequence in coordinator.data.get("sequences", []):
        sequence_name = sequence.get("name")
        if not sequence_name:
            continue
        entities.append(FarmBotSequenceButton(coordinator, sequence))

    async_add_entities(entities)


class FarmBotActionButton(FarmBotEntity, ButtonEntity):
    """Built-in FarmBot action button (celery_script command)."""

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
        """Execute action."""
        await self._action()
        await self.coordinator.async_request_refresh()


class FarmBotSequenceButton(FarmBotEntity, ButtonEntity):
    """Button for executing a user-defined FarmBot sequence."""

    def __init__(self, coordinator, sequence: dict) -> None:
        super().__init__(coordinator)
        self._sequence_name = sequence["name"]
        self._sequence_id = sequence.get("id")

        self._attr_unique_id = f"{DOMAIN}_sequence_{self._sequence_id}"
        self._attr_name = f"FarmBot Run {self._sequence_name}"
        self._attr_icon = _sequence_icon(self._sequence_name)

    @property
    def _current_sequence(self) -> dict | None:
        """Look up current sequence data by ID (handles renames)."""
        for seq in self.coordinator.data.get("sequences", []):
            if seq.get("id") == self._sequence_id:
                return seq
        return None

    @property
    def name(self) -> str:
        """Return current name (updates if sequence is renamed)."""
        seq = self._current_sequence
        if seq:
            return f"FarmBot Run {seq['name']}"
        return f"FarmBot Run {self._sequence_name}"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return sequence metadata."""
        seq = self._current_sequence
        if seq:
            return {
                "sequence_id": seq.get("id"),
                "sequence_name": seq.get("name"),
                "color": seq.get("color"),
                "pinned": seq.get("pinned", False),
                "steps": len(seq.get("body", [])),
            }
        return {"sequence_id": self._sequence_id}

    async def async_press(self) -> None:
        """Execute sequence by current name (handles renames)."""
        seq = self._current_sequence
        name = seq["name"] if seq else self._sequence_name
        await self.coordinator.async_execute_sequence(name)
        await self.coordinator.async_request_refresh()
