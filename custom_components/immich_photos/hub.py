"""Hub for Immich Photos integration."""
from __future__ import annotations

import logging
from urllib.parse import urljoin

import aiohttp

from homeassistant.exceptions import HomeAssistantError

_HEADER_API_KEY = "x-api-key"
_LOGGER = logging.getLogger(__name__)


class ImmichHub:
    """Immich API hub."""

    def __init__(self, host: str, api_key: str) -> None:
        self.host = host
        self.api_key = api_key

    @property
    def _headers(self) -> dict:
        return {"Accept": "application/json", _HEADER_API_KEY: self.api_key}

    async def authenticate(self) -> bool:
        """Validate connection and API key."""
        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.host, "/api/auth/validateToken")
                async with session.post(url=url, headers=self._headers) as response:
                    if response.status != 200:
                        return False
                    result = await response.json()
                    return bool(result.get("authStatus"))
        except aiohttp.ClientError as err:
            _LOGGER.error("Error connecting to Immich: %s", err)
            raise CannotConnect from err

    async def get_my_user_info(self) -> dict:
        """Get current user info."""
        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.host, "/api/users/me")
                async with session.get(url=url, headers=self._headers) as response:
                    if response.status != 200:
                        raise ApiError
                    return await response.json()
        except aiohttp.ClientError as err:
            raise CannotConnect from err

    async def list_all_albums(self) -> list[dict]:
        """List all albums."""
        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.host, "/api/albums")
                async with session.get(url=url, headers=self._headers) as response:
                    if response.status != 200:
                        raise ApiError
                    return await response.json()
        except aiohttp.ClientError as err:
            raise CannotConnect from err

    async def get_asset_thumbnail(self, asset_id: str) -> bytes | None:
        """Download preview thumbnail for an asset."""
        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.host, f"/api/assets/{asset_id}/thumbnail")
                headers = {**self._headers, "Accept": "image/jpeg,image/*"}
                async with session.get(url=url, params={"size": "preview"}, headers=headers) as response:
                    if response.status != 200:
                        return None
                    return await response.read()
        except aiohttp.ClientError as err:
            _LOGGER.error("Error fetching thumbnail: %s", err)
            return None

    async def search_assets(
        self,
        page: int = 1,
        size: int = 200,
        is_favorite: bool | None = None,
        album_id: str | None = None,
    ) -> list[dict]:
        """Search for image assets."""
        body: dict = {
            "type": "IMAGE",
            "isArchived": False,
            "isTrashed": False,
            "page": page,
            "size": size,
        }
        if is_favorite is not None:
            body["isFavorite"] = is_favorite
        if album_id:
            body["albumId"] = album_id

        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.host, "/api/search/metadata")
                async with session.post(url=url, headers=self._headers, json=body) as response:
                    if response.status != 200:
                        return []
                    data = await response.json()
                    return data.get("assets", {}).get("items", [])
        except aiohttp.ClientError as err:
            _LOGGER.error("Error searching assets: %s", err)
            return []


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class ApiError(HomeAssistantError):
    """Error to indicate that the API returned an error."""
