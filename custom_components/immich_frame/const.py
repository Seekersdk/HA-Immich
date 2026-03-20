"""Constants for the immich_frame integration."""

DOMAIN = "immich_frame"
CONF_WATCHED_ALBUMS = "watched_albums"

# Crop modes
CROP_MODE_ORIGINAL = "Original"
CROP_MODE_CROP = "Crop"
CROP_MODE_COMBINE = "Combine images"
CROP_MODES = [CROP_MODE_ORIGINAL, CROP_MODE_CROP, CROP_MODE_COMBINE]
DEFAULT_CROP_MODE = CROP_MODE_COMBINE

# Selection modes
SELECTION_MODE_RANDOM = "Random"
SELECTION_MODE_ORDER = "Album order"
SELECTION_MODES = [SELECTION_MODE_RANDOM, SELECTION_MODE_ORDER]
DEFAULT_SELECTION_MODE = SELECTION_MODE_RANDOM

# Update intervals
UPDATE_INTERVALS = [
    "15 seconds",
    "30 seconds",
    "1 minute",
    "5 minutes",
    "10 minutes",
    "30 minutes",
    "1 hour",
]
UPDATE_INTERVAL_MAP = {
    "15 seconds": 15,
    "30 seconds": 30,
    "1 minute": 60,
    "5 minutes": 300,
    "10 minutes": 600,
    "30 minutes": 1800,
    "1 hour": 3600,
}
DEFAULT_UPDATE_INTERVAL = "5 minutes"
