"""Immich API client."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, date
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class ImmichAsset:
    """Represents an Immich photo/video asset."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.id: str = data["id"]
        self.filename: str = data.get("originalFileName", "")
        self.type: str = data.get("type", "IMAGE")
        self.is_favorite: bool = data.get("isFavorite", False)
        self.is_archived: bool = data.get("isArchived", False)
        self.is_trashed: bool = data.get("isTrashed", False)

        # Parse creation date
        raw_date = data.get("fileCreatedAt") or data.get("localDateTime", "")
        try:
            self.created_at: datetime = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            self.created_at = datetime.min

        # EXIF / metadata
        exif = data.get("exifInfo") or {}
        self.width: int = exif.get("exifImageWidth") or data.get("exifInfo", {}).get("exifImageWidth", 0)
        self.height: int = exif.get("exifImageHeight") or data.get("exifInfo", {}).get("exifImageHeight", 0)

    @property
    def is_landscape(self) -> bool:
        """Return True if the image is landscape (wider than tall)."""
        if self.width > 0 and self.height > 0:
            return self.width > self.height
        return True  # Assume landscape if unknown

    @property
    def is_portrait(self) -> bool:
        return not self.is_landscape

    @property
    def aspect_ratio(self) -> float:
        if self.height > 0:
            return self.width / self.height
        return 1.0


class ImmichAlbum:
    """Represents an Immich album."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.id: str = data["id"]
        self.name: str = data.get("albumName", "Unknown")
        self.asset_count: int = data.get("assetCount", 0)


class ImmichApiClient:
    """Client for the Immich REST API."""

    def __init__(self, host: str, api_key: str, session: aiohttp.ClientSession) -> None:
        self._host = host.rstrip("/")
        self._api_key = api_key
        self._session = session

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "Accept": "application/json",
        }

    async def validate(self) -> bool:
        """Validate the connection and API key.

        Tries multiple endpoints to support different Immich versions.
        """
        # Try ping first (no auth needed) to verify connectivity
        for ping_path in ("/api/server/ping", "/api/server-info/ping"):
            try:
                async with self._session.get(
                    f"{self._host}{ping_path}",
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=False,
                ) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                continue
        else:
            # Neither ping endpoint worked — try auth endpoint directly
            pass

        # Now validate the API key
        for auth_path in ("/api/users/me", "/api/user/me", "/api/auth/validateToken"):
            try:
                async with self._session.get(
                    f"{self._host}{auth_path}",
                    headers=self._headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=False,
                ) as resp:
                    if resp.status == 401:
                        raise ImmichAuthError("Invalid API key")
                    if resp.status == 200:
                        return True
                    if resp.status == 405:
                        # Method not allowed — try POST for validateToken
                        async with self._session.post(
                            f"{self._host}/api/auth/validateToken",
                            headers=self._headers,
                            timeout=aiohttp.ClientTimeout(total=10),
                            ssl=False,
                        ) as post_resp:
                            if post_resp.status == 401:
                                raise ImmichAuthError("Invalid API key")
                            if post_resp.status == 200:
                                return True
            except ImmichAuthError:
                raise
            except Exception:
                continue

        raise ImmichConnectionError(f"Cannot connect to Immich at {self._host}")

    async def get_albums(self) -> list[ImmichAlbum]:
        """Get all albums for the current user."""
        try:
            async with self._session.get(
                f"{self._host}/api/albums",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=15),
                ssl=False,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return [ImmichAlbum(a) for a in data]
        except Exception as err:
            _LOGGER.error("Error fetching albums: %s", err)
            return []

    async def get_album_assets(self, album_id: str) -> list[ImmichAsset]:
        """Get all assets for a specific album."""
        try:
            async with self._session.get(
                f"{self._host}/api/albums/{album_id}?withoutAssets=false",
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=30),
                ssl=False,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                assets_raw = data.get("assets", [])
                return [
                    ImmichAsset(a) for a in assets_raw
                    if a.get("type") == "IMAGE" and not a.get("isTrashed")
                ]
        except Exception as err:
            _LOGGER.error("Error fetching album assets for %s: %s", album_id, err)
            return []

    async def search_random(
        self,
        count: int = 10,
        is_favorite: bool | None = None,
        album_id: str | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
    ) -> list[ImmichAsset]:
        """Get random images using the searchRandom endpoint."""
        body: dict[str, Any] = {"count": count, "type": "IMAGE", "isArchived": False, "isTrashed": False}
        if is_favorite is not None:
            body["isFavorite"] = is_favorite
        if album_id:
            body["albumId"] = album_id
        if after:
            body["takenAfter"] = after.isoformat()
        if before:
            body["takenBefore"] = before.isoformat()

        try:
            async with self._session.post(
                f"{self._host}/api/search/random",
                headers=self._headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=15),
                ssl=False,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                if isinstance(data, list):
                    return [ImmichAsset(a) for a in data]
                items = data.get("assets", {}).get("items", []) if isinstance(data, dict) else []
                return [ImmichAsset(a) for a in items]
        except Exception as err:
            _LOGGER.error("Error in searchRandom: %s", err)
            return []

    async def search_metadata(
        self,
        page: int = 1,
        size: int = 100,
        is_favorite: bool | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        album_id: str | None = None,
    ) -> tuple[list[ImmichAsset], int]:
        """Search assets using metadata search, returns (assets, total)."""
        body: dict[str, Any] = {
            "type": "IMAGE",
            "isArchived": False,
            "isTrashed": False,
            "page": page,
            "size": size,
            "withExif": True,
        }
        if is_favorite is not None:
            body["isFavorite"] = is_favorite
        if after:
            body["takenAfter"] = after.isoformat()
        if before:
            body["takenBefore"] = before.isoformat()
        if album_id:
            body["albumId"] = album_id

        try:
            async with self._session.post(
                f"{self._host}/api/search/metadata",
                headers=self._headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=30),
                ssl=False,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                items = data.get("assets", {}).get("items", [])
                total = data.get("assets", {}).get("total", len(items))
                return [ImmichAsset(a) for a in items], total
        except Exception as err:
            _LOGGER.error("Error in searchMetadata: %s", err)
            return [], 0

    async def get_asset_thumbnail(self, asset_id: str, size: str = "thumbnail") -> bytes | None:
        """Download a thumbnail/preview for an asset. size: thumbnail | preview"""
        try:
            async with self._session.get(
                f"{self._host}/api/assets/{asset_id}/thumbnail",
                params={"size": size},
                headers={**self._headers, "Accept": "image/jpeg,image/webp,image/*"},
                timeout=aiohttp.ClientTimeout(total=30),
                ssl=False,
            ) as resp:
                resp.raise_for_status()
                return await resp.read()
        except Exception as err:
            _LOGGER.error("Error fetching thumbnail for %s: %s", asset_id, err)
            return None

    async def get_asset_original(self, asset_id: str) -> bytes | None:
        """Download the original file for an asset."""
        try:
            async with self._session.get(
                f"{self._host}/api/assets/{asset_id}/original",
                headers={**self._headers, "Accept": "image/*"},
                timeout=aiohttp.ClientTimeout(total=60),
                ssl=False,
            ) as resp:
                resp.raise_for_status()
                return await resp.read()
        except Exception as err:
            _LOGGER.error("Error fetching original for %s: %s", asset_id, err)
            return None


class ImmichConnectionError(Exception):
    """Connection error."""


class ImmichAuthError(Exception):
    """Authentication error."""
