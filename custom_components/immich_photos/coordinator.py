"""DataUpdateCoordinator for Immich Photos."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, date
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ImmichApiClient, ImmichAsset
from .const import (
    DOMAIN,
    ALBUM_ID_ALL,
    ALBUM_ID_FAVORITES,
    MEDIA_CACHE_TTL,
    BATCH_SIZE,
)

_LOGGER = logging.getLogger(__name__)


class ImmichAlbumCoordinator(DataUpdateCoordinator):
    """Manages fetching and caching of assets for one album config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ImmichApiClient,
        album_id: str,
        album_name: str,
        update_interval_seconds: int = 300,
    ) -> None:
        self.client = client
        self.album_id = album_id
        self.album_name = album_name

        # Pool of assets available to pick from
        self._asset_pool: list[ImmichAsset] = []
        self._pool_fetched_at: datetime | None = None
        self._is_updating_pool: bool = False

        # Currently displayed asset(s)
        self.current_asset: ImmichAsset | None = None
        self.secondary_asset: ImmichAsset | None = None  # for combine images
        self.current_image_bytes: bytes | None = None

        # Settings (updated by selects)
        self.selection_mode: str = "Random"  # Random | Album order
        self.crop_mode: str = "Combine images"  # Original | Crop | Combine images
        self.date_filter_mode: str = "None"
        self.date_filter_after: datetime | None = None
        self.date_filter_before: datetime | None = None

        # Album order tracking
        self._album_order_index: int = 0

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{album_id}",
            update_interval=timedelta(seconds=update_interval_seconds),
        )

    @property
    def media_count(self) -> int:
        return len(self._asset_pool)

    @property
    def is_updating_pool(self) -> bool:
        return self._is_updating_pool

    def _pool_is_stale(self) -> bool:
        if self._pool_fetched_at is None:
            return True
        return (datetime.now() - self._pool_fetched_at).total_seconds() > MEDIA_CACHE_TTL

    async def _refresh_pool(self) -> None:
        """Refresh the asset pool from Immich."""
        if self._is_updating_pool:
            return

        self._is_updating_pool = True
        _LOGGER.debug("Refreshing asset pool for album %s", self.album_id)

        try:
            assets = await self._fetch_all_assets()
            self._asset_pool = assets
            self._pool_fetched_at = datetime.now()
            _LOGGER.info(
                "Loaded %d assets for album %s", len(self._asset_pool), self.album_name
            )
        except Exception as err:
            _LOGGER.error("Failed to refresh pool for %s: %s", self.album_name, err)
        finally:
            self._is_updating_pool = False

    async def _fetch_all_assets(self) -> list[ImmichAsset]:
        """Fetch all matching assets (paginated)."""
        is_favorite = True if self.album_id == ALBUM_ID_FAVORITES else None
        album_id_param = None if self.album_id in (ALBUM_ID_ALL, ALBUM_ID_FAVORITES) else self.album_id

        after = self._resolve_after()
        before = self._resolve_before()

        all_assets: list[ImmichAsset] = []
        page = 1

        while True:
            assets, total = await self.client.search_metadata(
                page=page,
                size=BATCH_SIZE,
                is_favorite=is_favorite,
                after=after,
                before=before,
                album_id=album_id_param,
            )
            all_assets.extend(assets)
            if not assets or len(all_assets) >= total or len(assets) < BATCH_SIZE:
                break
            page += 1

        return all_assets

    def _resolve_after(self) -> datetime | None:
        mode = self.date_filter_mode
        if mode == "None":
            return None
        if mode == "After date":
            return self.date_filter_after
        if mode == "Before date":
            return None
        if mode == "Between dates":
            return self.date_filter_after
        if mode == "This month":
            now = datetime.now()
            return datetime(now.year, now.month, 1)
        if mode == "This year":
            return datetime(datetime.now().year, 1, 1)
        return None

    def _resolve_before(self) -> datetime | None:
        mode = self.date_filter_mode
        if mode == "None":
            return None
        if mode == "After date":
            return None
        if mode == "Before date":
            return self.date_filter_before
        if mode == "Between dates":
            return self.date_filter_before
        if mode in ("This month", "This year"):
            return datetime.now()
        return None

    async def _async_update_data(self) -> dict[str, Any]:
        """Called by HA on the update interval — advance to next image."""
        if self._pool_is_stale():
            await self._refresh_pool()

        if not self._asset_pool:
            _LOGGER.warning("No assets in pool for %s", self.album_name)
            return self._state_dict()

        await self._pick_next()
        return self._state_dict()

    async def async_next_media(self, mode: str | None = None) -> None:
        """Manually advance to next media (service call)."""
        if mode:
            self.selection_mode = mode

        if self._pool_is_stale() or not self._asset_pool:
            await self._refresh_pool()

        if not self._asset_pool:
            return

        await self._pick_next()
        self.async_set_updated_data(self._state_dict())

    async def _pick_next(self) -> None:
        """Pick next asset(s) and render the image bytes."""
        if self.selection_mode == "Random":
            self.current_asset = random.choice(self._asset_pool)
        else:
            # Album order
            if self._album_order_index >= len(self._asset_pool):
                self._album_order_index = 0
            self.current_asset = self._asset_pool[self._album_order_index]
            self._album_order_index += 1

        self.secondary_asset = None

        # Determine if we should try to combine images
        if self.crop_mode == "Combine images" and self.current_asset.is_portrait:
            # Try to find a second portrait image to combine
            candidates = [a for a in self._asset_pool if a.id != self.current_asset.id and a.is_portrait]
            if candidates:
                self.secondary_asset = random.choice(candidates)

        # Fetch image bytes
        self.current_image_bytes = await self._render_image()

    async def _render_image(self) -> bytes | None:
        """Fetch and optionally combine image(s) into final bytes."""
        from .image_processor import process_image

        primary_bytes = await self.client.get_asset_thumbnail(
            self.current_asset.id, size="preview"
        )
        if primary_bytes is None:
            return None

        secondary_bytes = None
        if self.secondary_asset:
            secondary_bytes = await self.client.get_asset_thumbnail(
                self.secondary_asset.id, size="preview"
            )

        try:
            result = await self.hass.async_add_executor_job(
                process_image,
                primary_bytes,
                secondary_bytes,
                self.crop_mode,
                self.current_asset,
                self.secondary_asset,
            )
            return result
        except Exception as err:
            _LOGGER.error("Image processing error: %s", err)
            return primary_bytes  # fallback: return raw

    def _state_dict(self) -> dict[str, Any]:
        asset = self.current_asset
        return {
            "media_id": asset.id if asset else None,
            "filename": asset.filename if asset else None,
            "creation_timestamp": asset.created_at.isoformat() if asset else None,
            "media_count": len(self._asset_pool),
            "is_updating": self._is_updating_pool,
        }

    async def async_force_refresh_pool(self) -> None:
        """Force a refresh of the asset pool (e.g. after filter change)."""
        self._pool_fetched_at = None
        await self._refresh_pool()
