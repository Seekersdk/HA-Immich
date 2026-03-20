"""Hub for Immich Frame integration."""
from __future__ import annotations

import logging
from urllib.parse import urljoin

import aiohttp

from homeassistant.exceptions import HomeAssistantError

_HEADER_API_KEY = "x-api-key"
_LOGGER = logging.getLogger(__name__)
_ALLOWED_MIME_TYPES = ["image/png", "image/jpeg"]


class ImmichHub:
    def __init__(self, host: str, api_key: str) -> None:
        self.host = host
        self.api_key = api_key

    async def authenticate(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.host, "/api/auth/validateToken")
                headers = {"Accept": "application/json", _HEADER_API_KEY: self.api_key}
                async with session.post(url=url, headers=headers) as response:
                    if response.status != 200:
                        _LOGGER.error("Auth error: %s", await response.text())
                        return False
                    auth_result = await response.json()
                    return bool(auth_result.get("authStatus"))
        except aiohttp.ClientError as exception:
            _LOGGER.error("Error connecting: %s", exception)
            raise CannotConnect from exception

    async def get_my_user_info(self) -> dict:
        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.host, "/api/users/me")
                headers = {"Accept": "application/json", _HEADER_API_KEY: self.api_key}
                async with session.get(url=url, headers=headers) as response:
                    if response.status != 200:
                        raise ApiError()
                    return await response.json()
        except aiohttp.ClientError as exception:
            raise CannotConnect from exception

    async def get_asset_info(self, asset_id: str) -> dict | None:
        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.host, f"/api/assets/{asset_id}")
                headers = {"Accept": "application/json", _HEADER_API_KEY: self.api_key}
                async with session.get(url=url, headers=headers) as response:
                    if response.status != 200:
                        raise ApiError()
                    return await response.json()
        except aiohttp.ClientError as exception:
            raise CannotConnect from exception

    async def download_asset(self, asset_id: str) -> bytes | None:
        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.host, f"/api/assets/{asset_id}/original")
                headers = {_HEADER_API_KEY: self.api_key}
                async with session.get(url=url, headers=headers) as response:
                    if response.status != 200:
                        return None
                    if response.content_type not in _ALLOWED_MIME_TYPES:
                        _LOGGER.error("Unsupported MIME type: %s", response.content_type)
                        return None
                    return await response.read()
        except aiohttp.ClientError as exception:
            raise CannotConnect from exception

    async def list_favorite_images(self) -> list[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.host, "/api/search/metadata")
                headers = {"Accept": "application/json", _HEADER_API_KEY: self.api_key}
                async with session.post(url=url, headers=headers, data={"isFavorite": "true"}) as response:
                    if response.status != 200:
                        raise ApiError()
                    favorites = await response.json()
                    return [a for a in favorites["assets"]["items"] if a["type"] == "IMAGE"]
        except aiohttp.ClientError as exception:
            raise CannotConnect from exception

    async def list_all_albums(self) -> list[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.host, "/api/albums")
                headers = {"Accept": "application/json", _HEADER_API_KEY: self.api_key}
                async with session.get(url=url, headers=headers) as response:
                    if response.status != 200:
                        raise ApiError()
                    return await response.json()
        except aiohttp.ClientError as exception:
            raise CannotConnect from exception

    async def list_album_images(self, album_id: str) -> list[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.host, f"/api/albums/{album_id}")
                headers = {"Accept": "application/json", _HEADER_API_KEY: self.api_key}
                async with session.get(url=url, headers=headers) as response:
                    if response.status != 200:
                        raise ApiError()
                    album_info = await response.json()
                    return [a for a in album_info["assets"] if a["type"] == "IMAGE"]
        except aiohttp.ClientError as exception:
            raise CannotConnect from exception


class CannotConnect(HomeAssistantError):
    pass

class InvalidAuth(HomeAssistantError):
    pass

class ApiError(HomeAssistantError):
    pass
