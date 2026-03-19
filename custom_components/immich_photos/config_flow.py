"""Config flow for Immich Photos integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import ImmichApiClient, ImmichConnectionError, ImmichAuthError
from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_API_KEY,
    CONF_ALBUMS,
    ALBUM_ID_FAVORITES,
    ALBUM_VIRTUAL,
)

_LOGGER = logging.getLogger(__name__)


def _multi_select_validator(options: dict):
    valid_keys = set(options.keys())
    def _validate(value):
        if isinstance(value, list):
            invalid = [v for v in value if v not in valid_keys]
            if invalid:
                raise vol.Invalid(f"Invalid selection(s): {invalid}")
            return value
        raise vol.Invalid("Expected a list")
    return _validate


class ImmichPhotosConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str = ""
        self._api_key: str = ""
        self._available_albums: dict[str, str] = {}

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST].rstrip("/")
            self._api_key = user_input[CONF_API_KEY]

            try:
                async with aiohttp.ClientSession() as session:
                    client = ImmichApiClient(self._host, self._api_key, session)
                    await client.validate()
                    albums = await client.get_albums()
                    self._available_albums = {**ALBUM_VIRTUAL}
                    for a in albums:
                        self._available_albums[a.id] = a.name
            except ImmichAuthError:
                errors["base"] = "invalid_auth"
            except ImmichConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error connecting to Immich")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(self._host)
                self._abort_if_unique_id_configured()
                return await self.async_step_album()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default="http://192.168.1.100:2283"): str,
                vol.Required(CONF_API_KEY): str,
            }),
            errors=errors,
        )

    async def async_step_album(self, user_input=None):
        if user_input is not None:
            selected = user_input.get(CONF_ALBUMS, [ALBUM_ID_FAVORITES])
            return self.async_create_entry(
                title=f"Immich ({self._host})",
                data={
                    CONF_HOST: self._host,
                    CONF_API_KEY: self._api_key,
                    CONF_ALBUMS: selected,
                },
            )

        return self.async_show_form(
            step_id="album",
            data_schema=vol.Schema({
                vol.Required(CONF_ALBUMS, default=[ALBUM_ID_FAVORITES]): vol.All(
                    list, _multi_select_validator(self._available_albums)
                ),
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ImmichPhotosOptionsFlow(config_entry)


class ImmichPhotosOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry
        self._available_albums: dict[str, str] = {}

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data={CONF_ALBUMS: user_input.get(CONF_ALBUMS, [])})

        host = self._config_entry.data[CONF_HOST]
        api_key = self._config_entry.data[CONF_API_KEY]
        try:
            async with aiohttp.ClientSession() as session:
                client = ImmichApiClient(host, api_key, session)
                albums = await client.get_albums()
                self._available_albums = {**ALBUM_VIRTUAL}
                for a in albums:
                    self._available_albums[a.id] = a.name
        except Exception:
            self._available_albums = {**ALBUM_VIRTUAL}

        current = self._config_entry.options.get(
            CONF_ALBUMS, self._config_entry.data.get(CONF_ALBUMS, [ALBUM_ID_FAVORITES])
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_ALBUMS, default=current): vol.All(
                    list, _multi_select_validator(self._available_albums)
                ),
            }),
        )
