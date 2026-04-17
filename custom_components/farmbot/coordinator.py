"""Coordinator for FarmBot data."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientError
import farmbot

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import (
    CELERY_SCRIPT_ENDPOINT,
    CONF_SERVER,
    DEFAULT_UPDATE_INTERVAL,
    DEVICE_ENDPOINT,
    DOMAIN,
    IMAGES_ENDPOINT,
    SENSOR_READINGS_ENDPOINT,
    SEQUENCES_ENDPOINT,
    SERVICE_KIND_EMERGENCY_LOCK,
    SERVICE_KIND_EMERGENCY_UNLOCK,
    SERVICE_KIND_MOVE_ABSOLUTE,
    SERVICE_KIND_TAKE_PHOTO,
    SERVICE_KIND_WRITE_PIN,
    SERVICE_KIND_FIND_HOME,
    SERVICE_KIND_SYNC,
)

_LOGGER = logging.getLogger(__name__)


class FarmBotDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manage FarmBot API state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.hass = hass
        self.entry = entry
        self.email: str = entry.data[CONF_EMAIL]
        self.password: str = entry.data[CONF_PASSWORD]
        self.server: str = entry.data[CONF_SERVER].rstrip("/")
        self._token: str | None = None
        self._api_lock = asyncio.Lock()
        self._target_position: dict[str, float] = {"x": 0.0, "y": 0.0, "z": 0.0}

        update_interval = timedelta(
            seconds=entry.options.get("update_interval", DEFAULT_UPDATE_INTERVAL)
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_refresh_token(self) -> str:
        """Refresh and set API token."""
        token = await self.hass.async_add_executor_job(
            farmbot.get_token,
            self.email,
            self.password,
            self.server,
        )
        await self.hass.async_add_executor_job(farmbot.set_token, token)
        self._token = token
        return token

    async def _async_farmbot_call(self, func: Callable[..., Any], *args: Any) -> Any:
        """Run a farmbot library call in executor."""
        return await self.hass.async_add_executor_job(func, *args)

    @staticmethod
    def _is_auth_error(err: Exception) -> bool:
        """Best-effort check for authorization failures."""
        message = str(err).lower()
        return any(term in message for term in ("401", "403", "unauthorized", "forbidden", "token"))

    async def _async_api_call(self, func: Callable[..., Any], *args: Any) -> Any:
        """Execute an API call, refreshing token once on auth failures."""
        if self._token is None:
            async with self._api_lock:
                if self._token is None:
                    await self._async_refresh_token()

        try:
            return await self._async_farmbot_call(func, *args)
        except Exception as err:
            if not self._is_auth_error(err):
                raise

            _LOGGER.debug("FarmBot auth error detected; refreshing token")
            async with self._api_lock:
                await self._async_refresh_token()
            return await self._async_farmbot_call(func, *args)

    async def async_execute_sequence(self, sequence_name: str) -> None:
        """Run a named FarmBot sequence."""
        await self._async_api_call(farmbot.sequence, sequence_name)

    async def async_emergency_lock(self) -> None:
        """Trigger e-stop."""
        await self.async_run_celery_script(SERVICE_KIND_EMERGENCY_LOCK, {})

    async def async_emergency_unlock(self) -> None:
        """Clear e-stop."""
        await self.async_run_celery_script(SERVICE_KIND_EMERGENCY_UNLOCK, {})

    async def async_take_photo(self) -> None:
        """Trigger take photo action."""
        await self.async_run_celery_script(SERVICE_KIND_TAKE_PHOTO, {})

    async def async_find_home(self) -> None:
        """Execute find home (homing) command."""
        await self.async_run_celery_script(SERVICE_KIND_FIND_HOME, {"speed": 100, "axis": "all"})

    async def async_sync(self) -> None:
        """Trigger a sync."""
        await self.async_run_celery_script(SERVICE_KIND_SYNC, {})

    async def async_move_absolute(self, x: float, y: float, z: float) -> None:
        """Move FarmBot to an absolute XYZ target."""
        self._target_position = {"x": x, "y": y, "z": z}
        await self.async_run_celery_script(
            SERVICE_KIND_MOVE_ABSOLUTE,
            {
                "location": {"x": x, "y": y, "z": z},
                "offset": {"x": 0, "y": 0, "z": 0},
                "speed": 100,
            },
        )

    async def async_set_peripheral(self, pin_number: int, value: bool) -> None:
        """Set a peripheral output pin."""
        await self.async_run_celery_script(
            SERVICE_KIND_WRITE_PIN,
            {
                "pin_mode": 0,
                "pin_number": pin_number,
                "pin_value": 1 if value else 0,
            },
        )

    async def async_run_celery_script(self, kind: str, args: dict[str, Any]) -> None:
        """POST a celery_script command directly to FarmBot API."""
        if self._token is None:
            async with self._api_lock:
                if self._token is None:
                    await self._async_refresh_token()

        session = async_get_clientsession(self.hass)
        url = f"{self.server}/{CELERY_SCRIPT_ENDPOINT}"
        payload = {"kind": kind, "args": args, "body": []}
        headers = {"Authorization": f"Bearer {self._token}"}

        async def _post_request() -> int:
            async with session.post(url, json=payload, headers=headers) as response:
                await response.read()
                return response.status

        try:
            status = await _post_request()
            if status in (401, 403):
                async with self._api_lock:
                    await self._async_refresh_token()
                headers["Authorization"] = f"Bearer {self._token}"
                status = await _post_request()

            if status >= 400:
                raise UpdateFailed(f"Celery script call failed with status {status}")
        except ClientError as err:
            raise UpdateFailed(f"Celery script request failed: {err}") from err

    @staticmethod
    def _normalize_sequences(raw_sequences: Any) -> list[dict[str, Any]]:
        """Normalize sequence list payload."""
        if not isinstance(raw_sequences, list):
            return []
        sequences: list[dict[str, Any]] = []
        for item in raw_sequences:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not name:
                continue
            sequences.append(item)
        return sequences

    @staticmethod
    def _normalize_peripherals(device: Any) -> list[dict[str, Any]]:
        """Normalize peripheral payload from device data."""
        if not isinstance(device, dict):
            return []

        candidates = device.get("peripherals") or device.get("pins") or []
        if isinstance(candidates, dict):
            candidates = list(candidates.values())

        peripherals: list[dict[str, Any]] = []
        if not isinstance(candidates, list):
            return peripherals

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            pin_number = candidate.get("pin_number")
            if pin_number is None:
                continue
            peripherals.append(
                {
                    "id": candidate.get("id", pin_number),
                    "name": candidate.get("label")
                    or candidate.get("name")
                    or f"Peripheral {pin_number}",
                    "pin_number": pin_number,
                    "value": int(candidate.get("value", 0)),
                }
            )

        return peripherals

    @staticmethod
    def _extract_connected(device: Any) -> bool:
        """Extract connected state from device payload."""
        if not isinstance(device, dict):
            return False

        if (value := device.get("is_connected")) is not None:
            return bool(value)
        if (value := device.get("online")) is not None:
            return bool(value)

        bot = device.get("bot")
        if isinstance(bot, dict):
            for key in ("is_online", "mqtt_connected", "connected"):
                if key in bot:
                    return bool(bot[key])

        return False

    @staticmethod
    def _extract_estopped(device: Any) -> bool:
        """Extract emergency stop state from device payload."""
        if not isinstance(device, dict):
            return False

        for key in ("is_emergency_lock", "emergency_lock", "estopped", "locked"):
            if key in device:
                return bool(device[key])

        bot = device.get("bot")
        if isinstance(bot, dict):
            for key in ("is_emergency_lock", "emergency_lock", "locked"):
                if key in bot:
                    return bool(bot[key])

        return False

    @staticmethod
    def _latest_image(images: Any) -> dict[str, Any] | None:
        """Extract latest image object."""
        if not isinstance(images, list) or not images:
            return None

        valid = [image for image in images if isinstance(image, dict)]
        if not valid:
            return None

        valid.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return valid[0]

    @staticmethod
    def _coerce_float(value: Any) -> float:
        """Coerce value to float."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _latest_soil_readings(readings: Any) -> dict[str, dict[str, Any]]:
        """Return the latest reading grouped by sensor key."""
        if not isinstance(readings, list):
            return {}

        latest: dict[str, dict[str, Any]] = {}

        for reading in readings:
            if not isinstance(reading, dict):
                continue

            sensor_key = str(
                reading.get("pin")
                or reading.get("pin_number")
                or reading.get("name")
                or reading.get("id")
                or "unknown"
            )
            current = latest.get(sensor_key)
            if current is None or str(reading.get("created_at", "")) > str(
                current.get("created_at", "")
            ):
                latest[sensor_key] = reading

        return latest

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and aggregate FarmBot data."""
        try:
            device, sequences, position, images, sensor_readings = await asyncio.gather(
                self._async_api_call(farmbot.api_get, DEVICE_ENDPOINT),
                self._async_api_call(farmbot.api_get, SEQUENCES_ENDPOINT),
                self._async_api_call(farmbot.get_xyz),
                self._async_api_call(farmbot.api_get, IMAGES_ENDPOINT),
                self._async_api_call(farmbot.api_get, SENSOR_READINGS_ENDPOINT),
            )
        except Exception as err:
            raise UpdateFailed(f"Error communicating with FarmBot API: {err}") from err

        sequences_list = self._normalize_sequences(sequences)
        sequences_by_slug = {
            slugify(sequence["name"]): sequence for sequence in sequences_list if "name" in sequence
        }

        position_data = position if isinstance(position, dict) else {}
        current_x = self._coerce_float(position_data.get("x"))
        current_y = self._coerce_float(position_data.get("y"))
        current_z = self._coerce_float(position_data.get("z"))

        if self._target_position == {"x": 0.0, "y": 0.0, "z": 0.0}:
            self._target_position = {"x": current_x, "y": current_y, "z": current_z}

        latest_image = self._latest_image(images)

        data = {
            "device": device if isinstance(device, dict) else {},
            "sequences": sequences_list,
            "sequences_by_slug": sequences_by_slug,
            "position": {"x": current_x, "y": current_y, "z": current_z},
            "connected": self._extract_connected(device),
            "estopped": self._extract_estopped(device),
            "images": images if isinstance(images, list) else [],
            "latest_image": latest_image,
            "soil_readings": self._latest_soil_readings(sensor_readings),
            "peripherals": self._normalize_peripherals(device),
            "fbos_version": (device or {}).get("fbos_version")
            or (device or {}).get("os_version"),
            "firmware_version": (device or {}).get("firmware_version")
            or (device or {}).get("firmware_hardware"),
            "target_position": dict(self._target_position),
        }
        return data
