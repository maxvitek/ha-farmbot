"""Shared test helpers."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.farmbot.const import DOMAIN


async def setup_integration(hass, data: dict) -> MockConfigEntry:
    """Create and set up a FarmBot config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
