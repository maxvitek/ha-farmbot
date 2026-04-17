"""Entity and platform tests for FarmBot."""

from __future__ import annotations

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN

from .common import setup_integration


async def test_backwards_compatible_entities(hass, farmbot_credentials, mock_farmbot):
    """Ensure existing automation entity IDs still exist."""
    await setup_integration(hass, farmbot_credentials)

    assert hass.states.get("button.run_find_home") is not None
    assert hass.states.get("button.run_water_everything") is not None
    assert hass.states.get("sensor.farmbot_position_x") is not None
    assert hass.states.get("sensor.farmbot_position_y") is not None
    assert hass.states.get("sensor.farmbot_position_z") is not None
    assert hass.states.get("sensor.farmbot_sequences_count") is not None
    assert hass.states.get("sensor.farmbot_sequences_list") is not None


async def test_sequence_button_press_calls_sequence(hass, farmbot_credentials, mock_farmbot):
    """Test pressing a dynamic sequence button executes sequence."""
    await setup_integration(hass, farmbot_credentials)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        "press",
        {"entity_id": "button.run_water_everything"},
        blocking=True,
    )

    mock_farmbot.sequence.assert_any_call("Water Everything")


async def test_switch_and_number_actions(hass, farmbot_credentials, mock_farmbot, aioclient_mock):
    """Test peripheral switch write and coordinate move number."""
    aioclient_mock.post("https://my.farm.bot/api/celery_script", status=200)

    await setup_integration(hass, farmbot_credentials)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.farmbot_water_valve"},
        blocking=True,
    )

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {"entity_id": "number.farmbot_target_x", "value": 42},
        blocking=True,
    )

    post_calls = aioclient_mock.mock_calls
    assert post_calls


async def test_sequences_list_attributes(hass, farmbot_credentials, mock_farmbot):
    """Ensure sequences list sensor carries sequence details."""
    await setup_integration(hass, farmbot_credentials)

    state = hass.states.get("sensor.farmbot_sequences_list")
    assert state is not None
    assert "sequences" in state.attributes
    assert len(state.attributes["sequences"]) == 3
