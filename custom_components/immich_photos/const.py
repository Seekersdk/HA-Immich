"""Constants for the Immich Photos integration."""

DOMAIN = "immich_photos"

CONF_HOST = "host"
CONF_API_KEY = "api_key"
CONF_ALBUMS = "albums"

# Album IDs
ALBUM_ID_ALL = "__all__"
ALBUM_ID_FAVORITES = "__favorites__"

ALBUM_VIRTUAL = {
    ALBUM_ID_ALL: "All Photos",
    ALBUM_ID_FAVORITES: "Favorites",
}

# Entity attributes
ATTR_MEDIA_ID = "media_id"
ATTR_FILENAME = "filename"
ATTR_CREATION_TIMESTAMP = "creation_timestamp"
ATTR_MEDIA_COUNT = "media_count"
ATTR_IS_UPDATING = "is_updating"

# Select options
IMAGE_SELECTION_MODES = ["Random", "Album order"]
CROP_MODES = ["Original", "Crop", "Combine images"]
UPDATE_INTERVALS = ["1 minute", "5 minutes", "10 minutes", "30 minutes", "1 hour"]

UPDATE_INTERVAL_MAP = {
    "1 minute": 60,
    "5 minutes": 300,
    "10 minutes": 600,
    "30 minutes": 1800,
    "1 hour": 3600,
}

# Default values
DEFAULT_UPDATE_INTERVAL = "5 minutes"
DEFAULT_CROP_MODE = "Combine images"
DEFAULT_SELECTION_MODE = "Random"
DEFAULT_DATE_FILTER = "None"

# Cache
MEDIA_CACHE_TTL = 3 * 3600  # 3 hours
BATCH_SIZE = 100

# Combine images threshold (aspect ratio)
LANDSCAPE_RATIO_THRESHOLD = 1.0  # width > height

# Image output size for combined view
COMBINED_IMAGE_WIDTH = 2048
COMBINED_IMAGE_HEIGHT = 1024
SINGLE_IMAGE_WIDTH = 1024
SINGLE_IMAGE_HEIGHT = 768
