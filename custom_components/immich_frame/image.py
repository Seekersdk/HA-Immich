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

from .const import (
    DOMAIN,
    CONF_WATCHED_ALBUMS,
    CROP_MODE_ORIGINAL,
    CROP_MODE_CROP,
    CROP_MODE_COMBINE,
    SELECTION_MODE_ORDER,
    UPDATE_INTERVAL_MAP,
    DEFAULT_UPDATE_INTERVAL,
)
from .hub import ImmichHub

try:
    from PIL import Image as PilImage, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Poll every 30s — actual image change governed by selected interval
SCAN_INTERVAL = timedelta(seconds=30)
_POOL_REFRESH_INTERVAL = timedelta(hours=12)
_MAX_COMBINE_ATTEMPTS = 5

# Fixed output portrait ratio for Combine mode (width:height = 3:4)
_PORTRAIT_W = 3
_PORTRAIT_H = 4

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    hub: ImmichHub = data["hub"]
    entry_state = data["state"]

    entities: list[BaseImmichImage] = [ImmichImageFavorite(hass, hub, entry_state)]

    watched_albums = config_entry.options.get(CONF_WATCHED_ALBUMS, [])
    try:
        all_albums = await hub.list_all_albums()
        entities += [
            ImmichImageAlbum(hass, hub, entry_state, album["id"], album["albumName"])
            for album in all_albums
            if album["id"] in watched_albums
        ]
    except Exception:
        pass

    data["image_entities"] = entities
    async_add_entities(entities)
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(config_entry.entry_id)


# ---------------------------------------------------------------------------
# Image processing helpers
# ---------------------------------------------------------------------------

def _open_with_exif(img_bytes: bytes) -> "PilImage.Image":
    """Open image and apply EXIF rotation so dimensions are correct."""
    img = PilImage.open(io.BytesIO(img_bytes))
    return ImageOps.exif_transpose(img)


def _is_landscape(img_bytes: bytes) -> bool:
    img = _open_with_exif(img_bytes)
    return img.width > img.height


def _crop_to_ratio(img: "PilImage.Image", ratio_w: int, ratio_h: int) -> "PilImage.Image":
    """Center-crop image to fill exact aspect ratio (cover mode)."""
    target_ratio = ratio_w / ratio_h
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        # Wider than target — crop left/right
        new_w = int(img.height * target_ratio)
        left = (img.width - new_w) // 2
        return img.crop((left, 0, left + new_w, img.height))
    else:
        # Taller than target — crop top/bottom
        new_h = int(img.width / target_ratio)
        top = (img.height - new_h) // 2
        return img.crop((0, top, img.width, top + new_h))


def _stack_vertically(img1_bytes: bytes, img2_bytes: bytes) -> bytes:
    """Stack two images vertically at same width (raw, before portrait crop)."""
    img1 = _open_with_exif(img1_bytes).convert("RGB")
    img2 = _open_with_exif(img2_bytes).convert("RGB")

    w = max(img1.width, img2.width)
    if img1.width != w:
        img1 = img1.resize((w, int(img1.height * w / img1.width)), PilImage.LANCZOS)
    if img2.width != w:
        img2 = img2.resize((w, int(img2.height * w / img2.width)), PilImage.LANCZOS)

    combined = PilImage.new("RGB", (w, img1.height + img2.height))
    combined.paste(img1, (0, 0))
    combined.paste(img2, (0, img1.height))
    return combined


def _to_portrait_frame(img: "PilImage.Image") -> bytes:
    """Crop image to fixed 3:4 portrait frame and return JPEG bytes."""
    img = _crop_to_ratio(img, _PORTRAIT_W, _PORTRAIT_H)
    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=85)
    return out.getvalue()


def _center_crop_to_portrait(img_bytes: bytes) -> bytes:
    """Crop mode: center-crop to 3:4 portrait."""
    img = _open_with_exif(img_bytes).convert("RGB")
    return _to_portrait_frame(img)


# ---------------------------------------------------------------------------
# Base entity
# ---------------------------------------------------------------------------

class BaseImmichImage(ImageEntity):
    _attr_has_entity_name = True
    _attr_should_poll = True

    def __init__(self, hass: HomeAssistant, hub: ImmichHub, entry_state) -> None:
        super().__init__(hass=hass, verify_ssl=True)
        self.hub = hub
        self.hass = hass
        self._entry_state = entry_state
        self._current_image_bytes: bytes | None = None
        self._cached_asset_ids: list[str] | None = None
        self._pool_updated = None
        self._pool_index: int = 0
        self._last_image_load = None
        self._attr_extra_state_attributes: dict = {}

    async def async_update(self) -> None:
        interval = UPDATE_INTERVAL_MAP.get(
            self._entry_state.update_interval,
            UPDATE_INTERVAL_MAP[DEFAULT_UPDATE_INTERVAL],
        )
        now = dt_util.utcnow()
        if (
            self._last_image_load is None
            or (now - self._last_image_load).total_seconds() >= interval
        ):
            await self._load_next_image()

    async def async_image(self) -> bytes | None:
        if not self._current_image_bytes:
            await self._load_next_image()
        return self._current_image_bytes

    async def _refresh_pool(self) -> list[str]:
        raise NotImplementedError

    async def _ensure_pool(self) -> None:
        now = dt_util.utcnow()
        if (
            self._pool_updated is None
            or (now - self._pool_updated) > _POOL_REFRESH_INTERVAL
        ):
            self._cached_asset_ids = await self._refresh_pool()
            self._pool_updated = now
            self._pool_index = 0
            _LOGGER.debug("%s: pool refreshed (%d assets)", self.name, len(self._cached_asset_ids or []))

    def _pick_next(self, exclude: str | None = None) -> str | None:
        pool = self._cached_asset_ids
        if not pool:
            return None
        if self._entry_state.selection_mode == SELECTION_MODE_ORDER:
            idx = self._pool_index % len(pool)
            self._pool_index += 1
            return pool[idx]
        candidates = [a for a in pool if a != exclude] if exclude and len(pool) > 1 else pool
        return random.choice(candidates)

    def _pick_random(self, exclude: str | None = None) -> str | None:
        pool = self._cached_asset_ids
        if not pool:
            return None
        candidates = [a for a in pool if a != exclude] if exclude and len(pool) > 1 else pool
        return random.choice(candidates)

    async def _load_next_image(self) -> None:
        await self._ensure_pool()

        asset_id = self._pick_next()
        if not asset_id:
            _LOGGER.warning("%s: no assets in pool", self.name)
            return

        img_bytes = await self.hub.get_thumbnail(asset_id)
        if not img_bytes:
            return

        crop_mode = self._entry_state.crop_mode

        if HAS_PIL:
            try:
                if crop_mode == CROP_MODE_COMBINE:
                    if _is_landscape(img_bytes):
                        # Try to combine with another landscape
                        combined_img = await self._find_and_combine(img_bytes, asset_id)
                    else:
                        combined_img = _open_with_exif(img_bytes).convert("RGB")
                    # Always crop to fixed portrait frame
                    img_bytes = _to_portrait_frame(combined_img)

                elif crop_mode == CROP_MODE_CROP:
                    img_bytes = _center_crop_to_portrait(img_bytes)

                # CROP_MODE_ORIGINAL: serve as-is

            except Exception as err:
                _LOGGER.warning("%s: image processing failed: %s", self.name, err)

        asset_info = await self.hub.get_asset_info(asset_id)
        if asset_info:
            self._attr_extra_state_attributes["media_filename"] = asset_info.get("originalFileName") or ""
            self._attr_extra_state_attributes["media_localdatetime"] = asset_info.get("localDateTime") or ""

        self._current_image_bytes = img_bytes
        self._last_image_load = dt_util.utcnow()
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    async def _find_and_combine(self, first_bytes: bytes, first_id: str) -> "PilImage.Image":
        """Try to find second landscape and stack. Returns PIL Image (not yet portrait-cropped)."""
        for attempt in range(_MAX_COMBINE_ATTEMPTS):
            second_id = self._pick_random(exclude=first_id)
            if not second_id:
                break
            second_bytes = await self.hub.get_thumbnail(second_id)
            if second_bytes and _is_landscape(second_bytes):
                _LOGGER.debug("%s: combining (attempt %d)", self.name, attempt + 1)
                return _stack_vertically(first_bytes, second_bytes)
        _LOGGER.debug("%s: no second landscape, showing single", self.name)
        return _open_with_exif(first_bytes).convert("RGB")


class ImmichImageFavorite(BaseImmichImage):
    _attr_unique_id = "immich_frame_favorite_image"
    _attr_name = "Immich Frame: Random favorite image"

    async def _refresh_pool(self) -> list[str]:
        return [img["id"] for img in await self.hub.list_favorite_images()]


class ImmichImageAlbum(BaseImmichImage):
    def __init__(self, hass, hub, entry_state, album_id: str, album_name: str):
        super().__init__(hass, hub, entry_state)
        self._album_id = album_id
        self._attr_unique_id = f"immich_frame_{album_id}"
        self._attr_name = f"Immich Frame: {album_name}"

    async def _refresh_pool(self) -> list[str]:
        return [img["id"] for img in await self.hub.list_album_images(self._album_id)]
