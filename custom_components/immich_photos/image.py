"""Image entities for Immich Photos."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
import random

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ALBUMS, DOMAIN
from .hub import ImmichHub

SCAN_INTERVAL = timedelta(minutes=5)
_POOL_REFRESH_INTERVAL = timedelta(hours=3)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Immich Photos image platform."""
    hub: ImmichHub = hass.data[DOMAIN][config_entry.entry_id]

    selected = config_entry.data.get(CONF_ALBUMS, ["__favorites__"])
    entities: list[ImmichImageBase] = []

    try:
        all_albums = await hub.list_all_albums()
        album_map = {a["id"]: a["albumName"] for a in all_albums}
    except Exception:
        album_map = {}

    for album_id in selected:
        if album_id == "__favorites__":
            entities.append(ImmichImageFavorites(hass, hub))
        elif album_id == "__all__":
            entities.append(ImmichImageAll(hass, hub))
        elif album_id in album_map:
            entities.append(ImmichImageAlbum(hass, hub, album_id, album_map[album_id]))

    async_add_entities(entities)

    config_entry.async_on_unload(
        config_entry.add_update_listener(_update_listener)
    )


async def _update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(config_entry.entry_id)


class ImmichImageBase(ImageEntity):
    """Base image entity for Immich Photos."""

    _attr_has_entity_name = True
    _attr_should_poll = True

    def __init__(self, hass: HomeAssistant, hub: ImmichHub) -> None:
        super().__init__(hass=hass, verify_ssl=True)
        self.hub = hub
        self._pool: list[str] = []
        self._pool_updated: datetime | None = None
        self._current_bytes: bytes | None = None
        self._attr_extra_state_attributes: dict = {}

    async def _fetch_pool(self) -> list[str]:
        raise NotImplementedError

    async def _ensure_pool(self) -> None:
        if (
            not self._pool_updated
            or (datetime.now() - self._pool_updated) > _POOL_REFRESH_INTERVAL
        ):
            assets = await self._fetch_pool()
            self._pool = [a["id"] for a in assets]
            self._pool_updated = datetime.now()
            _LOGGER.debug("%s: pool refreshed with %d assets", self.name, len(self._pool))

    async def async_update(self) -> None:
        await self._load_next_image()

    async def async_image(self) -> bytes | None:
        if not self._current_bytes:
            await self._load_next_image()
        return self._current_bytes

    async def _load_next_image(self) -> None:
        await self._ensure_pool()
        if not self._pool:
            _LOGGER.warning("%s: no assets in pool", self.name)
            return

        asset_id = random.choice(self._pool)
        data = await self.hub.get_asset_thumbnail(asset_id)
        if data:
            self._current_bytes = data
            self._attr_image_last_updated = datetime.now()
            self._attr_extra_state_attributes["asset_id"] = asset_id
            self.async_write_ha_state()


class ImmichImageFavorites(ImmichImageBase):
    """Random image from favorites."""

    _attr_unique_id = "immich_photos_favorites"
    _attr_name = "Immich Favorites"

    async def _fetch_pool(self) -> list[dict]:
        return await self.hub.search_assets(is_favorite=True)


class ImmichImageAll(ImmichImageBase):
    """Random image from all photos."""

    _attr_unique_id = "immich_photos_all"
    _attr_name = "Immich All Photos"

    async def _fetch_pool(self) -> list[dict]:
        return await self.hub.search_assets()


class ImmichImageAlbum(ImmichImageBase):
    """Random image from a specific album."""

    def __init__(self, hass: HomeAssistant, hub: ImmichHub, album_id: str, album_name: str) -> None:
        super().__init__(hass, hub)
        self._album_id = album_id
        self._attr_unique_id = f"immich_photos_{album_id}"
        self._attr_name = f"Immich {album_name}"

    async def _fetch_pool(self) -> list[dict]:
        return await self.hub.search_assets(album_id=self._album_id)
