"""Image entities for Immich Frame."""
from __future__ import annotations

import io
from datetime import timedelta
import logging
import random

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_WATCHED_ALBUMS
from .hub import ImmichHub

try:
    from PIL import Image as PilImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

SCAN_INTERVAL = timedelta(minutes=5)
_ID_LIST_REFRESH_INTERVAL = timedelta(hours=12)
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    hub = ImmichHub(
        host=config_entry.data[CONF_HOST], api_key=config_entry.data[CONF_API_KEY]
    )
    async_add_entities([ImmichImageFavorite(hass, hub)])
    watched_albums = config_entry.options.get(CONF_WATCHED_ALBUMS, [])
    async_add_entities(
        [
            ImmichImageAlbum(hass, hub, album_id=album["id"], album_name=album["albumName"])
            for album in await hub.list_all_albums()
            if album["id"] in watched_albums
        ]
    )
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(config_entry.entry_id)


def _stack_vertically(img1_bytes: bytes, img2_bytes: bytes) -> bytes:
    """Stack two images vertically, scaled to same width."""
    img1 = PilImage.open(io.BytesIO(img1_bytes)).convert("RGB")
    img2 = PilImage.open(io.BytesIO(img2_bytes)).convert("RGB")

    target_width = max(img1.width, img2.width)

    if img1.width != target_width:
        ratio = target_width / img1.width
        img1 = img1.resize((target_width, int(img1.height * ratio)), PilImage.LANCZOS)
    if img2.width != target_width:
        ratio = target_width / img2.width
        img2 = img2.resize((target_width, int(img2.height * ratio)), PilImage.LANCZOS)

    combined = PilImage.new("RGB", (target_width, img1.height + img2.height))
    combined.paste(img1, (0, 0))
    combined.paste(img2, (0, img1.height))

    output = io.BytesIO()
    combined.save(output, format="JPEG", quality=85)
    return output.getvalue()


def _is_landscape(img_bytes: bytes) -> bool:
    """Return True if image is wider than tall."""
    img = PilImage.open(io.BytesIO(img_bytes))
    return img.width > img.height


class BaseImmichImage(ImageEntity):
    _attr_has_entity_name = True
    _attr_should_poll = True
    _current_image_bytes: bytes | None = None
    _cached_available_asset_ids: list[str] | None = None
    _available_asset_ids_last_updated = None

    def __init__(self, hass: HomeAssistant, hub: ImmichHub) -> None:
        super().__init__(hass=hass, verify_ssl=True)
        self.hub = hub
        self.hass = hass
        self._attr_extra_state_attributes = {}

    async def async_update(self) -> None:
        await self._load_next_image()

    async def async_image(self) -> bytes | None:
        if not self._current_image_bytes:
            await self._load_next_image()
        return self._current_image_bytes

    async def _refresh_available_asset_ids(self) -> list[str] | None:
        raise NotImplementedError

    async def _get_next_asset_id(self, exclude: str | None = None) -> str | None:
        now = dt_util.utcnow()
        if (
            not self._available_asset_ids_last_updated
            or (now - self._available_asset_ids_last_updated) > _ID_LIST_REFRESH_INTERVAL
        ):
            _LOGGER.debug("%s: refreshing asset pool", self.name)
            self._cached_available_asset_ids = await self._refresh_available_asset_ids()
            self._available_asset_ids_last_updated = now

        if not self._cached_available_asset_ids:
            _LOGGER.warning("%s: no assets in pool", self.name)
            return None

        pool = self._cached_available_asset_ids
        if exclude and len(pool) > 1:
            pool = [a for a in pool if a != exclude]

        return random.choice(pool)

    async def _load_next_image(self) -> None:
        asset_id = await self._get_next_asset_id()
        if not asset_id:
            return

        img_bytes = await self.hub.get_thumbnail(asset_id)
        if not img_bytes:
            return

        # Combine two landscape images vertically into portrait frame
        if HAS_PIL:
            try:
                if _is_landscape(img_bytes):
                    second_id = await self._get_next_asset_id(exclude=asset_id)
                    if second_id:
                        second_bytes = await self.hub.get_thumbnail(second_id)
                        if second_bytes and _is_landscape(second_bytes):
                            img_bytes = _stack_vertically(img_bytes, second_bytes)
                            _LOGGER.debug("%s: combined two landscape images", self.name)
            except Exception as err:
                _LOGGER.warning("%s: combine failed, using single image: %s", self.name, err)

        asset_info = await self.hub.get_asset_info(asset_id)
        if asset_info:
            self._attr_extra_state_attributes["media_filename"] = (
                asset_info.get("originalFileName") or ""
            )
            self._attr_extra_state_attributes["media_localdatetime"] = (
                asset_info.get("localDateTime") or ""
            )

        self._current_image_bytes = img_bytes
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()


class ImmichImageFavorite(BaseImmichImage):
    _attr_unique_id = "immich_frame_favorite_image"
    _attr_name = "Immich Frame: Random favorite image"

    async def _refresh_available_asset_ids(self) -> list[str] | None:
        return [image["id"] for image in await self.hub.list_favorite_images()]


class ImmichImageAlbum(BaseImmichImage):
    def __init__(self, hass, hub, album_id, album_name):
        super().__init__(hass, hub)
        self._album_id = album_id
        self._attr_unique_id = f"immich_frame_{album_id}"
        self._attr_name = f"Immich Frame: {album_name}"

    async def _refresh_available_asset_ids(self) -> list[str] | None:
        return [
            image["id"] for image in await self.hub.list_album_images(self._album_id)
        ]
