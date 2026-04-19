"""Camera platform for FarmBot."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from aiohttp import ClientError

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .entity import FarmBotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FarmBot camera entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([FarmBotLatestImageCamera(coordinator)])


class FarmBotLatestImageCamera(FarmBotEntity, Camera):
    """Camera exposing the latest FarmBot image."""

    _attr_unique_id = f"{DOMAIN}_latest_image"
    _attr_name = "FarmBot Latest Image"

    def __init__(self, coordinator) -> None:
        """Initialize camera with both parent classes."""
        FarmBotEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._cached_sweep_key: str | None = None
        self._cached_montage: bytes | None = None
        self._cached_grid_size: list[int] | None = None

    @property
    def is_on(self) -> bool:
        """Return true when a latest image URL is available."""
        return self._image_url is not None

    @property
    def _image_url(self) -> str | None:
        image = self.coordinator.data.get("latest_image")
        if not isinstance(image, dict):
            return None
        return image.get("attachment_url") or image.get("url")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose sweep metadata when a sweep is available."""
        sweep = self._sweep_data
        if not sweep:
            return None

        grid_size = self._grid_size_for_sweep(sweep.get("images", []))
        if self._cached_sweep_key == sweep.get("key") and self._cached_grid_size:
            grid_size = self._cached_grid_size

        return {
            "sweep_date": sweep.get("sweep_date"),
            "image_count": sweep.get("image_count"),
            "grid_size": grid_size,
        }

    @property
    def _sweep_data(self) -> dict[str, Any] | None:
        sweep = self.coordinator.data.get("latest_sweep")
        if not isinstance(sweep, dict):
            return None
        images = sweep.get("images")
        if not isinstance(images, list) or len(images) < 5:
            return None
        return sweep

    @staticmethod
    def _extract_xy(image: dict[str, Any]) -> tuple[float, float] | None:
        meta = image.get("meta")
        if not isinstance(meta, dict):
            return None
        try:
            return float(meta["x"]), float(meta["y"])
        except (KeyError, TypeError, ValueError):
            return None

    @classmethod
    def _grid_size_for_sweep(cls, images: list[dict[str, Any]]) -> list[int] | None:
        coordinates = [cls._extract_xy(image) for image in images]
        if any(coord is None for coord in coordinates):
            return None
        x_values = sorted({coord[0] for coord in coordinates if coord is not None})
        y_values = sorted({coord[1] for coord in coordinates if coord is not None})
        if not x_values or not y_values:
            return None
        return [len(x_values), len(y_values)]

    async def _async_fetch_image(self, url: str) -> bytes | None:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url) as response:
                if response.status >= 400:
                    return None
                return await response.read()
        except ClientError:
            return None

    @staticmethod
    def _compose_montage(tiles: list[tuple[tuple[float, float], bytes]]) -> tuple[bytes, list[int]] | None:
        try:
            from PIL import Image
        except ImportError:
            return None

        x_values = sorted({xy[0] for xy, _ in tiles})
        y_values = sorted({xy[1] for xy, _ in tiles})
        if not x_values or not y_values:
            return None

        x_index = {x: idx for idx, x in enumerate(x_values)}
        y_index = {y: idx for idx, y in enumerate(y_values)}
        cell_width = 320
        cell_height = 240
        montage = Image.new(
            "RGB",
            (len(x_values) * cell_width, len(y_values) * cell_height),
        )

        for xy, image_bytes in tiles:
            with Image.open(BytesIO(image_bytes)) as image:
                normalized = image.convert("RGB").resize((cell_width, cell_height))
                montage.paste(
                    normalized,
                    (x_index[xy[0]] * cell_width, y_index[xy[1]] * cell_height),
                )

        output = BytesIO()
        montage.save(output, format="JPEG")
        return output.getvalue(), [len(x_values), len(y_values)]

    async def _async_generate_montage(self, images: list[dict[str, Any]]) -> tuple[bytes, list[int]] | None:
        download_plan: list[tuple[tuple[float, float], str]] = []
        for image in images:
            if not isinstance(image, dict):
                return None
            xy = self._extract_xy(image)
            image_url = image.get("attachment_url") or image.get("url")
            if xy is None or not image_url:
                return None
            download_plan.append((xy, image_url))

        tiles: list[tuple[tuple[float, float], bytes]] = []
        for xy, image_url in download_plan:
            image_bytes = await self._async_fetch_image(image_url)
            if image_bytes is None:
                return None
            tiles.append((xy, image_bytes))

        try:
            return await self.hass.async_add_executor_job(self._compose_montage, tiles)
        except Exception:
            return None

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Return latest image bytes or a stitched sweep montage."""
        sweep = self._sweep_data
        if sweep:
            sweep_key = sweep.get("key")
            if sweep_key and sweep_key == self._cached_sweep_key and self._cached_montage:
                return self._cached_montage

            composed = await self._async_generate_montage(sweep["images"])
            if composed is not None:
                montage_bytes, grid_size = composed
                self._cached_sweep_key = sweep_key
                self._cached_montage = montage_bytes
                self._cached_grid_size = grid_size
                return montage_bytes

        image_url = self._image_url
        if not image_url:
            return None
        return await self._async_fetch_image(image_url)
