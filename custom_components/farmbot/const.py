"""Constants for the FarmBot integration."""

from __future__ import annotations

DOMAIN = "farmbot"
DEFAULT_NAME = "FarmBot"
DEFAULT_UPDATE_INTERVAL = 60

CONF_SERVER = "server"
DEFAULT_SERVER = "https://my.farm.bot"

MANUFACTURER = "FarmBot Inc."
MODEL = "Genesis"

DATA_COORDINATOR = "coordinator"

CELERY_SCRIPT_ENDPOINT = "api/celery_script"
IMAGES_ENDPOINT = "images"
SEQUENCES_ENDPOINT = "sequences"
DEVICE_ENDPOINT = "device"
SENSOR_READINGS_ENDPOINT = "sensor_readings"

ATTR_SEQUENCES = "sequences"
ATTR_SOIL_READING = "reading"
ATTR_SOIL_READING_AT = "reading_at"

SERVICE_KIND_EMERGENCY_LOCK = "emergency_lock"
SERVICE_KIND_EMERGENCY_UNLOCK = "emergency_unlock"
SERVICE_KIND_MOVE_ABSOLUTE = "move_absolute"
SERVICE_KIND_TAKE_PHOTO = "take_photo"
SERVICE_KIND_WRITE_PIN = "write_pin"
