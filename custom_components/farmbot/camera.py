"""Camera platform for FarmBot."""

from __future__ import annotations

from io import BytesIO
import logging
from typing import Any

from aiohttp import ClientError

_LOGGER = logging.getLogger(__name__)
_MAX_MONTAGE_IMAGES = 30
# FarmBot reports photo positions with sub-mm jitter (e.g. x=1266.6 vs 1266.2);
# positions closer than this (mm) are the same grid line.
_GRID_TOLERANCE_MM = 10.0
_MAX_CANVAS_EDGE = 4096

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

    @staticmethod
    def _grid_lines(values: list[float]) -> list[float]:
        """Cluster jittery coordinates into grid lines (one per photo row/column)."""
        lines: list[list[float]] = []
        for value in sorted(values):
            if lines and value - lines[-1][-1] <= _GRID_TOLERANCE_MM:
                lines[-1].append(value)
            else:
                lines.append([value])
        return [sum(line) / len(line) for line in lines]

    @staticmethod
    def _nearest_index(lines: list[float], value: float) -> int:
        return min(range(len(lines)), key=lambda i: abs(lines[i] - value))

    @classmethod
    def _grid_size_for_sweep(cls, images: list[dict[str, Any]]) -> list[int] | None:
        coordinates = [cls._extract_xy(image) for image in images]
        if any(coord is None for coord in coordinates):
            return None
        x_lines = cls._grid_lines([coord[0] for coord in coordinates if coord is not None])
        y_lines = cls._grid_lines([coord[1] for coord in coordinates if coord is not None])
        if not x_lines or not y_lines:
            return None
        return [len(x_lines), len(y_lines)]

    async def _async_fetch_image(self, url: str) -> bytes | None:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(url) as response:
                if response.status >= 400:
                    return None
                return await response.read()
        except ClientError:
            return None

    @classmethod
    def _compose_montage(cls, tiles: list[tuple[tuple[float, float], bytes]]) -> tuple[bytes, list[int]] | None:
        """Compose a montage from geo-located image tiles.

        Coordinates are clustered into grid lines (tolerating FarmBot's position
        jitter) and each photo is placed by its row/column index.  The grid is
        therefore at most one cell per photo in each direction, and the canvas
        is capped at _MAX_CANVAS_EDGE px per edge (~50 MB RGB worst case).
        """
        try:
            from PIL import Image
        except ImportError:
            return None

        if not tiles:
            return None

        x_lines = cls._grid_lines([xy[0] for xy, _ in tiles])
        y_lines = cls._grid_lines([xy[1] for xy, _ in tiles])
        cols, rows = len(x_lines), len(y_lines)

        if cols == 1 and rows == 1:
            # All images at the same spot — just return the first one
            return tiles[0][1], [1, 1]

        cell_width = max(1, min(320, _MAX_CANVAS_EDGE // cols))
        cell_height = max(1, min(240, _MAX_CANVAS_EDGE // rows))
        canvas_w = cols * cell_width
        canvas_h = rows * cell_height
        if canvas_w > _MAX_CANVAS_EDGE or canvas_h > _MAX_CANVAS_EDGE:
            _LOGGER.warning("Montage grid %sx%s too large, skipping", cols, rows)
            return None
        montage = Image.new("RGB", (canvas_w, canvas_h))

        for xy, image_bytes in tiles:
            col = cls._nearest_index(x_lines, xy[0])
            row = cls._nearest_index(y_lines, xy[1])
            with Image.open(BytesIO(image_bytes)) as image:
                image.draft("RGB", (cell_width, cell_height))  # JPEG: decode at reduced size
                normalized = image.convert("RGB").resize((cell_width, cell_height))
                montage.paste(normalized, (col * cell_width, row * cell_height))

        output = BytesIO()
        montage.save(output, format="JPEG", quality=85)
        return output.getvalue(), [cols, rows]

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
                _LOGGER.debug("Returning cached montage for sweep %s", sweep_key)
                return self._cached_montage

            images = sweep["images"]
            if len(images) > _MAX_MONTAGE_IMAGES:
                _LOGGER.warning(
                    "Sweep has %d images (max %d) — using latest %d for montage",
                    len(images), _MAX_MONTAGE_IMAGES, _MAX_MONTAGE_IMAGES,
                )
                images = images[-_MAX_MONTAGE_IMAGES:]

            _LOGGER.info("Generating montage from %d images", len(images))
            try:
                composed = await self._async_generate_montage(images)
            except Exception:
                _LOGGER.exception("Montage generation failed")
                composed = None

            if composed is not None:
                montage_bytes, grid_size = composed
                self._cached_sweep_key = sweep_key
                self._cached_montage = montage_bytes
                self._cached_grid_size = grid_size
                _LOGGER.info("Montage generated: %d bytes, grid %s", len(montage_bytes), grid_size)
                return montage_bytes
            else:
                _LOGGER.warning("Montage generation failed, falling back to single image")

        image_url = self._image_url
        if not image_url:
            return None
        return await self._async_fetch_image(image_url)
