"""Sensor platform for FarmBot."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_SEQUENCES, ATTR_SOIL_READING, ATTR_SOIL_READING_AT, DATA_COORDINATOR, DOMAIN
from .entity import FarmBotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FarmBot sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[SensorEntity] = [
        FarmBotPositionSensor(coordinator, "x"),
        FarmBotPositionSensor(coordinator, "y"),
        FarmBotPositionSensor(coordinator, "z"),
        FarmBotSequencesCountSensor(coordinator),
        FarmBotSequencesListSensor(coordinator),
    ]

    for sensor_key in sorted(coordinator.data.get("soil_readings", {})):
        entities.append(FarmBotSoilReadingSensor(coordinator, sensor_key))

    async_add_entities(entities)


class FarmBotPositionSensor(FarmBotEntity, SensorEntity):
    """FarmBot XYZ position sensor."""

    _attr_native_unit_of_measurement = "mm"

    def __init__(self, coordinator, axis: str) -> None:
        super().__init__(coordinator)
        self._axis = axis
        self._attr_unique_id = f"{DOMAIN}_position_{axis}"
        self._attr_name = f"FarmBot Position {axis.upper()}"
        self.entity_id = f"sensor.farmbot_position_{axis}"

    @property
    def native_value(self) -> float:
        """Return current axis position."""
        return float(self.coordinator.data.get("position", {}).get(self._axis, 0.0))


class FarmBotSequencesCountSensor(FarmBotEntity, SensorEntity):
    """FarmBot sequence count sensor."""

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_sequences_count"
        self._attr_name = "FarmBot Sequences Count"
        self.entity_id = "sensor.farmbot_sequences_count"

    @property
    def native_value(self) -> int:
        """Return number of available sequences."""
        return len(self.coordinator.data.get("sequences", []))


class FarmBotSequencesListSensor(FarmBotEntity, SensorEntity):
    """FarmBot sequence list sensor."""

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_sequences_list"
        self._attr_name = "FarmBot Sequences List"
        self.entity_id = "sensor.farmbot_sequences_list"

    @property
    def native_value(self) -> int:
        """Return count of sequences (full list in attributes)."""
        return len(self.coordinator.data.get("sequences", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return sequence summary (name, id, color only — no body/steps to stay under 16KB)."""
        sequences = self.coordinator.data.get("sequences", [])
        summary = [
            {"id": s.get("id"), "name": s.get("name"), "color": s.get("color")}
            for s in sequences
        ]
        return {ATTR_SEQUENCES: summary}


class FarmBotSoilReadingSensor(FarmBotEntity, SensorEntity):
    """Latest soil reading sensor for a sensor key."""

    def __init__(self, coordinator, sensor_key: str) -> None:
        super().__init__(coordinator)
        self._sensor_key = sensor_key
        self._attr_unique_id = f"{DOMAIN}_soil_{sensor_key}"
        self._attr_name = f"FarmBot Soil Sensor {sensor_key}"

    @property
    def native_value(self) -> float | int | None:
        """Return latest soil reading value."""
        reading = self.coordinator.data.get("soil_readings", {}).get(self._sensor_key, {})
        return reading.get("value")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return metadata for the latest soil reading."""
        reading = self.coordinator.data.get("soil_readings", {}).get(self._sensor_key, {})
        return {
            ATTR_SOIL_READING: reading,
            ATTR_SOIL_READING_AT: reading.get("created_at"),
        }
