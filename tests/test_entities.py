"""Entity and platform tests for FarmBot."""

from __future__ import annotations

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN

from .common import setup_integration


async def test_builtin_action_buttons_exist(hass, farmbot_credentials, mock_farmbot):
    """Ensure built-in action buttons are created."""
    await setup_integration(hass, farmbot_credentials)

    assert hass.states.get("button.farmbot_find_home") is not None
    assert hass.states.get("button.farmbot_e_stop") is not None
    assert hass.states.get("button.farmbot_unlock") is not None
    assert hass.states.get("button.farmbot_take_photo") is not None
    assert hass.states.get("button.farmbot_sync") is not None


async def test_sequence_buttons_exist(hass, farmbot_credentials, mock_farmbot):
    """Ensure dynamic sequence buttons are created."""
    await setup_integration(hass, farmbot_credentials)

    # "Find Home" sequence still gets a button (separate from the built-in action)
    assert hass.states.get("button.farmbot_run_find_home") is not None
    assert hass.states.get("button.farmbot_run_water_everything") is not None
    assert hass.states.get("button.farmbot_run_do_maintenance") is not None


async def test_sensor_entities_exist(hass, farmbot_credentials, mock_farmbot):
    """Ensure sensor entities are created with correct values."""
    await setup_integration(hass, farmbot_credentials)

    pos_x = hass.states.get("sensor.farmbot_position_x")
    assert pos_x is not None
    assert float(pos_x.state) == 100.0

    pos_y = hass.states.get("sensor.farmbot_position_y")
    assert pos_y is not None
    assert float(pos_y.state) == 200.0

    pos_z = hass.states.get("sensor.farmbot_position_z")
    assert pos_z is not None
    assert float(pos_z.state) == -10.0

    assert hass.states.get("sensor.farmbot_sequences_count") is not None
    assert hass.states.get("sensor.farmbot_sequences_list") is not None


async def test_sequence_button_press_calls_sequence(hass, farmbot_credentials, mock_farmbot):
    """Test pressing a dynamic sequence button executes sequence."""
    await setup_integration(hass, farmbot_credentials)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        "press",
        {"entity_id": "button.farmbot_run_water_everything"},
        blocking=True,
    )

    mock_farmbot.sequence.assert_any_call("Water Everything")


async def test_find_home_action_button(hass, farmbot_credentials, mock_farmbot, aioclient_mock):
    """Test built-in Find Home button sends celery_script command."""
    aioclient_mock.post("https://my.farm.bot/api/celery_script", status=200)

    await setup_integration(hass, farmbot_credentials)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        "press",
        {"entity_id": "button.farmbot_find_home"},
        blocking=True,
    )

    assert aioclient_mock.mock_calls


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

    assert aioclient_mock.mock_calls


async def test_sequences_list_attributes(hass, farmbot_credentials, mock_farmbot):
    """Ensure sequences list sensor carries sequence details."""
    await setup_integration(hass, farmbot_credentials)

    state = hass.states.get("sensor.farmbot_sequences_list")
    assert state is not None
    assert "sequences" in state.attributes
    assert len(state.attributes["sequences"]) == 3
