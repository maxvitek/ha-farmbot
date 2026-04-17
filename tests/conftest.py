"""Test fixtures for FarmBot integration."""

from __future__ import annotations

import sys
import types
from unittest.mock import Mock

import pytest

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from custom_components.farmbot.const import CONF_SERVER, DEFAULT_SERVER


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in tests."""


@pytest.fixture
def farmbot_credentials() -> dict[str, str]:
    """Return sample FarmBot credentials."""
    return {
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "secret",
        CONF_SERVER: DEFAULT_SERVER,
    }


@pytest.fixture
def mock_farmbot(monkeypatch):
    """Mock farmbot sync library module."""
    module = types.SimpleNamespace()

    module.get_token = Mock(return_value="token-1")
    module.set_token = Mock(return_value=None)
    module.get_xyz = Mock(return_value={"x": 100.0, "y": 200.0, "z": -10.0})
    module.sequence = Mock(return_value=None)

    def _api_get(endpoint: str):
        if endpoint == "device":
            return {
                "id": 1,
                "name": "FarmBot",
                "is_connected": True,
                "is_emergency_lock": False,
                "fbos_version": "14.2.0",
                "firmware_version": "10.1.0",
                "peripherals": [
                    {"id": 101, "label": "Water Valve", "pin_number": 8, "value": 1},
                    {"id": 102, "label": "Vacuum", "pin_number": 9, "value": 0},
                ],
            }
        if endpoint == "sequences":
            return [
                {"id": 1, "name": "Find Home"},
                {"id": 2, "name": "Water Everything"},
                {"id": 3, "name": "Do Maintenance"},
            ]
        if endpoint == "images":
            return [
                {
                    "id": 10,
                    "attachment_url": "https://example.com/latest.jpg",
                    "created_at": "2026-01-02T00:00:00Z",
                }
            ]
        if endpoint == "sensor_readings":
            return [
                {"id": 11, "pin": 59, "value": 320, "created_at": "2026-01-01T00:00:00Z"},
                {"id": 12, "pin": 59, "value": 330, "created_at": "2026-01-02T00:00:00Z"},
                {"id": 13, "pin": 60, "value": 410, "created_at": "2026-01-02T00:00:00Z"},
            ]
        return {}

    module.api_get = Mock(side_effect=_api_get)

    monkeypatch.setitem(sys.modules, "farmbot", module)
    return module
