"""Coordinator for FarmBot data."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from farmbot import Farmbot

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import CONF_SERVER, DEFAULT_UPDATE_INTERVAL, DOMAIN

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
        self._fb = Farmbot()
        self._token: str | None = None
        self._api_lock = asyncio.Lock()

        update_interval = timedelta(
            seconds=entry.options.get("update_interval", DEFAULT_UPDATE_INTERVAL)
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_ensure_token(self) -> None:
        """Ensure we have a valid token, refresh if needed."""
        if self._token is not None:
            return
        async with self._api_lock:
            if self._token is not None:
                return
            await self._async_refresh_token()

    async def _async_refresh_token(self) -> None:
        """Refresh API token."""
        token = await self.hass.async_add_executor_job(
            self._fb.get_token, self.email, self.password, self.server
        )
        await self.hass.async_add_executor_job(self._fb.set_token, token)
        self._token = token

    @staticmethod
    def _is_auth_error(err: Exception) -> bool:
        """Check for authorization failures."""
        message = str(err).lower()
        return any(term in message for term in ("401", "403", "unauthorized", "forbidden", "token"))

    async def _async_api_call(self, method_name: str, *args: Any) -> Any:
        """Execute a Farmbot method, refreshing token once on auth failures."""
        await self._async_ensure_token()
        func = getattr(self._fb, method_name)
        try:
            return await self.hass.async_add_executor_job(func, *args)
        except Exception as err:
            if not self._is_auth_error(err):
                raise
            _LOGGER.debug("FarmBot auth error; refreshing token and retrying")
            async with self._api_lock:
                self._token = None
                await self._async_refresh_token()
            func = getattr(self._fb, method_name)
            return await self.hass.async_add_executor_job(func, *args)

    # --- Action methods ---

    async def async_execute_sequence(self, sequence_name: str) -> None:
        """Run a named FarmBot sequence."""
        await self._async_api_call("sequence", sequence_name)

    async def async_find_home(self) -> None:
        """Execute find home (homing) command."""
        await self._async_api_call("find_home")

    async def async_emergency_lock(self) -> None:
        """Trigger e-stop."""
        await self._async_api_call("e_stop")

    async def async_emergency_unlock(self) -> None:
        """Clear e-stop."""
        await self._async_api_call("unlock")

    async def async_take_photo(self) -> None:
        """Trigger take photo."""
        await self._async_api_call("take_photo")

    async def async_sync(self) -> None:
        """Trigger a sync (read_status refreshes the bot state)."""
        await self._async_api_call("read_status")

    async def async_move_absolute(self, x: float, y: float, z: float) -> None:
        """Move FarmBot to an absolute XYZ target."""
        await self._async_api_call("move", x, y, z)

    async def async_set_peripheral(self, pin_number: int, value: bool) -> None:
        """Set a peripheral output pin."""
        await self._async_api_call("write_pin", pin_number, 1 if value else 0, 0)

    # --- Data parsing helpers ---

    @staticmethod
    def _coerce_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _normalize_sequences(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict) and item.get("name")]

    @staticmethod
    def _extract_connected(device: Any) -> bool:
        if not isinstance(device, dict):
            return False
        for key in ("is_connected", "online"):
            if key in device:
                return bool(device[key])
        return False

    @staticmethod
    def _extract_estopped(device: Any) -> bool:
        if not isinstance(device, dict):
            return False
        for key in ("is_emergency_lock", "emergency_lock", "estopped", "locked"):
            if key in device:
                return bool(device[key])
        return False

    @staticmethod
    def _extract_peripherals(device: Any) -> list[dict[str, Any]]:
        if not isinstance(device, dict):
            return []
        candidates = device.get("peripherals") or device.get("pins") or []
        if isinstance(candidates, dict):
            candidates = list(candidates.values())
        if not isinstance(candidates, list):
            return []
        peripherals = []
        for c in candidates:
            if not isinstance(c, dict):
                continue
            pin = c.get("pin_number") or c.get("pin")
            if pin is None:
                continue
            peripherals.append({
                "id": c.get("id", pin),
                "name": c.get("label") or c.get("name") or f"Peripheral {pin}",
                "pin_number": int(pin),
                "value": int(c.get("value", 0)),
            })
        return peripherals

    @staticmethod
    def _latest_image(images: Any) -> dict[str, Any] | None:
        if not isinstance(images, list) or not images:
            return None
        valid = [img for img in images if isinstance(img, dict)]
        if not valid:
            return None
        valid.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
        return valid[0]

    @staticmethod
    def _latest_soil_readings(readings: Any) -> dict[str, dict[str, Any]]:
        if not isinstance(readings, list):
            return {}
        latest: dict[str, dict[str, Any]] = {}
        for r in readings:
            if not isinstance(r, dict):
                continue
            key = str(r.get("pin") or r.get("pin_number") or r.get("id") or "unknown")
            current = latest.get(key)
            if current is None or str(r.get("created_at", "")) > str(current.get("created_at", "")):
                latest[key] = r
        return latest

    # --- Main update ---

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and aggregate FarmBot data."""
        try:
            device, sequences, position, images, sensor_readings = await asyncio.gather(
                self._async_api_call("api_get", "device"),
                self._async_api_call("api_get", "sequences"),
                self._async_api_call("get_xyz"),
                self._async_api_call("api_get", "images"),
                self._async_api_call("api_get", "sensor_readings"),
            )
        except Exception as err:
            raise UpdateFailed(f"Error communicating with FarmBot API: {err}") from err

        sequences_list = self._normalize_sequences(sequences)
        position_data = position if isinstance(position, dict) else {}

        return {
            "device": device if isinstance(device, dict) else {},
            "sequences": sequences_list,
            "sequences_by_slug": {
                slugify(s["name"]): s for s in sequences_list if "name" in s
            },
            "position": {
                "x": self._coerce_float(position_data.get("x")),
                "y": self._coerce_float(position_data.get("y")),
                "z": self._coerce_float(position_data.get("z")),
            },
            "connected": self._extract_connected(device),
            "estopped": self._extract_estopped(device),
            "peripherals": self._extract_peripherals(device),
            "images": images if isinstance(images, list) else [],
            "latest_image": self._latest_image(images),
            "soil_readings": self._latest_soil_readings(sensor_readings),
            "fbos_version": (device or {}).get("fbos_version") or (device or {}).get("os_version"),
            "firmware_version": (device or {}).get("firmware_version") or (device or {}).get("firmware_hardware"),
        }
