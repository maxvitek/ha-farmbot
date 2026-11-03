"""Camera tests for FarmBot."""

from __future__ import annotations

from homeassistant.components.camera import async_get_image
from homeassistant.helpers import entity_registry as er

from .common import setup_integration

_GIF_1X1_RED = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\x00\x00\x00\x00\x00!"
    b"\xf9\x04\x01\n\x00\x01\x00,\x00\x00\x00\x00\x01\x00\x01\x00"
    b"\x00\x02\x02D\x01\x00;"
)


def _build_sweep_images() -> list[dict]:
    return [
        {
            "id": 100,
            "attachment_url": "https://example.com/sweep_100.jpg",
            "meta": {"x": 100, "y": 200, "z": -300},
            "created_at": "2026-04-18T14:00:00Z",
        },
        {
            "id": 101,
            "attachment_url": "https://example.com/sweep_101.jpg",
            "meta": {"x": 400, "y": 200, "z": -300},
            "created_at": "2026-04-18T14:00:30Z",
        },
        {
            "id": 102,
            "attachment_url": "https://example.com/sweep_102.jpg",
            "meta": {"x": 100, "y": 500, "z": -300},
            "created_at": "2026-04-18T14:01:00Z",
        },
        {
            "id": 103,
            "attachment_url": "https://example.com/sweep_103.jpg",
            "meta": {"x": 400, "y": 500, "z": -300},
            "created_at": "2026-04-18T14:01:30Z",
        },
        {
            "id": 104,
            "attachment_url": "https://example.com/sweep_104.jpg",
            "meta": {"x": 100, "y": 800, "z": -300},
            "created_at": "2026-04-18T14:02:00Z",
        },
        {
            "id": 105,
            "attachment_url": "https://example.com/sweep_105.jpg",
            "meta": {"x": 400, "y": 800, "z": -300},
            "created_at": "2026-04-18T14:02:30Z",
        },
    ]


async def test_camera_entity_loads(hass, farmbot_credentials, mock_farmbot, aioclient_mock):
    """Test latest image camera entity is created."""
    aioclient_mock.get("https://example.com/latest.jpg", content=b"jpgbytes", status=200)

    await setup_integration(hass, farmbot_credentials)

    registry = er.async_get(hass)
    entry = registry.async_get("camera.farmbot_latest_image")
    assert entry is not None


async def test_camera_generates_and_caches_montage(
    hass, farmbot_credentials, mock_farmbot, aioclient_mock
):
    """Test montage generation, sweep detection, and cache reuse."""
    original_api_get = mock_farmbot.api_get.side_effect

    def _api_get(endpoint: str):
        if endpoint == "images":
            return _build_sweep_images()
        return original_api_get(endpoint)

    mock_farmbot.api_get.side_effect = _api_get

    for image in _build_sweep_images():
        aioclient_mock.get(image["attachment_url"], content=_GIF_1X1_RED, status=200)

    await setup_integration(hass, farmbot_credentials)

    first = await async_get_image(hass, "camera.farmbot_latest_image")
    second = await async_get_image(hass, "camera.farmbot_latest_image")

    assert first.content.startswith(b"\xff\xd8")
    assert second.content == first.content

    state = hass.states.get("camera.farmbot_latest_image")
    assert state is not None
    assert state.attributes["sweep_date"] == "2026-04-18"
    assert state.attributes["image_count"] == 6
    assert state.attributes["grid_size"] == [2, 3]


async def test_camera_falls_back_to_latest_image_when_montage_fails(
    hass, farmbot_credentials, mock_farmbot, aioclient_mock
):
    """Test camera falls back to latest image if montage generation fails."""
    original_api_get = mock_farmbot.api_get.side_effect

    def _api_get(endpoint: str):
        if endpoint == "images":
            return _build_sweep_images()
        return original_api_get(endpoint)

    mock_farmbot.api_get.side_effect = _api_get

    sweep_images = _build_sweep_images()
    aioclient_mock.get(sweep_images[0]["attachment_url"], status=500)
    for image in sweep_images[1:-1]:
        aioclient_mock.get(image["attachment_url"], content=_GIF_1X1_RED, status=200)

    latest_url = sweep_images[-1]["attachment_url"]
    aioclient_mock.get(latest_url, content=b"single-latest", status=200)

    await setup_integration(hass, farmbot_credentials)
    image = await async_get_image(hass, "camera.farmbot_latest_image")

    assert image.content == b"single-latest"


def test_montage_tolerates_position_jitter():
    """Sub-mm FarmBot position jitter must not explode the montage canvas.

    Real sweep data has x=1266.6 vs 1266.2 for the same column; treating the
    0.4 mm gap as the grid step produced a multi-GB canvas and OOM-killed HA.
    """
    from io import BytesIO

    from PIL import Image

    from custom_components.farmbot.camera import FarmBotLatestImageCamera

    buf = BytesIO()
    Image.new("RGB", (1280, 960), (0, 128, 0)).save(buf, format="JPEG")
    jpeg = buf.getvalue()

    tiles = []
    for col, x in enumerate((0.0, 450.0, 900.0, 1350.0)):
        for y in (138.4, 373.8, 608.8, 844.2, 1079.4, 1315.0, 1549.0):
            jitter = 0.4 if (col + int(y)) % 2 else 0.0
            tiles.append(((x + jitter, y), jpeg))

    composed = FarmBotLatestImageCamera._compose_montage(tiles)
    assert composed is not None
    montage_bytes, grid = composed
    assert grid == [4, 7]
    with Image.open(BytesIO(montage_bytes)) as montage:
        assert montage.width <= 4096 and montage.height <= 4096
        assert montage.size == (4 * 320, 7 * 240)
    assert FarmBotLatestImageCamera._grid_size_for_sweep(
        [{"meta": {"x": xy[0], "y": xy[1]}} for xy, _ in tiles]
    ) == [4, 7]
