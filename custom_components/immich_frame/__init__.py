"""The immich_frame integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    CONF_WATCHED_ALBUMS,
    DEFAULT_CROP_MODE,
    DEFAULT_SELECTION_MODE,
    DEFAULT_UPDATE_INTERVAL,
)
from .hub import ImmichHub, InvalidAuth

PLATFORMS: list[Platform] = [Platform.IMAGE, Platform.SELECT, Platform.SENSOR]


class AlbumState:
    """Mutable state for a single album — shared between image, select and sensor entities."""

    def __init__(self, album_id: str, album_name: str) -> None:
        self.album_id = album_id
        self.album_name = album_name
        # Select state
        self.crop_mode: str = DEFAULT_CROP_MODE
        self.selection_mode: str = DEFAULT_SELECTION_MODE
        self.update_interval: str = DEFAULT_UPDATE_INTERVAL
        # Current media metadata (updated by image entity)
        self.current_filename: str = ""
        self.current_datetime: str = ""
        self.pool_count: int = 0
        # Entity references
        self.image_entities: list = []
        self.sensor_entities: list = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up immich_frame from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    hub = ImmichHub(host=entry.data[CONF_HOST], api_key=entry.data[CONF_API_KEY])
    if not await hub.authenticate():
        raise InvalidAuth

    try:
        all_albums = await hub.list_all_albums()
        album_name_map = {a["id"]: a["albumName"] for a in all_albums}
    except Exception:
        album_name_map = {}

    watched = entry.options.get(CONF_WATCHED_ALBUMS, [])
    album_states: dict[str, AlbumState] = {
        "__favorites__": AlbumState("__favorites__", "Favorites")
    }
    for album_id in watched:
        name = album_name_map.get(album_id, album_id)
        album_states[album_id] = AlbumState(album_id, name)

    hass.data[DOMAIN][entry.entry_id] = {
        "hub": hub,
        "album_states": album_states,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
