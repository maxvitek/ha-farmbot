"""Test fixtures for FarmBot integration."""

from __future__ import annotations

from unittest.mock import Mock, patch, MagicMock

import pytest

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from custom_components.farmbot.const import CONF_SERVER, DEFAULT_SERVER


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
            {"id": 1, "name": "Find Home", "body": [], "color": "green"},
            {"id": 2, "name": "Water Everything", "body": [{"kind": "move"}], "color": "blue"},
            {"id": 3, "name": "Do Maintenance", "body": [], "color": "red"},
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
def mock_farmbot():
    """Mock the Farmbot class from the farmbot library."""
    mock_instance = MagicMock()
    mock_instance.get_token.return_value = "token-1"
    mock_instance.set_token.return_value = None
    mock_instance.get_xyz.return_value = {"x": 100.0, "y": 200.0, "z": -10.0}
    mock_instance.sequence.return_value = None
    mock_instance.find_home.return_value = None
    mock_instance.e_stop.return_value = None
    mock_instance.unlock.return_value = None
    mock_instance.take_photo.return_value = None
    mock_instance.read_status.return_value = None
    mock_instance.move.return_value = None
    mock_instance.write_pin.return_value = None
    mock_instance.api_get.side_effect = _api_get

    with patch("custom_components.farmbot.coordinator.Farmbot", return_value=mock_instance), \
         patch("custom_components.farmbot.config_flow.Farmbot", return_value=mock_instance):
        yield mock_instance
