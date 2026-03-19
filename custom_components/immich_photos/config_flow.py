"""Config flow for Immich Photos integration."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from url_normalize import url_normalize
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import CONF_ALBUMS, DOMAIN
from .hub import CannotConnect, ImmichHub, InvalidAuth

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Required(CONF_API_KEY): str,
})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate credentials and return title + normalized data."""
    url = url_normalize(data[CONF_HOST])
    api_key = data[CONF_API_KEY]
    hub = ImmichHub(host=url, api_key=api_key)
    if not await hub.authenticate():
        raise InvalidAuth
    user_info = await hub.get_my_user_info()
    username = user_info.get("name", "Immich")
    hostname = urlparse(url).hostname
    return {"title": f"{username} @ {hostname}", "host": url, "api_key": api_key}


class ImmichPhotosConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Immich Photos."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str = ""
        self._api_key: str = ""
        self._title: str = ""
        self._album_map: dict[str, str] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                self._host = info["host"]
                self._api_key = info["api_key"]
                self._title = info["title"]
                try:
                    hub = ImmichHub(host=self._host, api_key=self._api_key)
                    albums = await hub.list_all_albums()
                    self._album_map = {
                        "__favorites__": "Favorites",
                        "__all__": "All Photos",
                    }
                    self._album_map.update({a["id"]: a["albumName"] for a in albums})
                except Exception:
                    self._album_map = {"__favorites__": "Favorites", "__all__": "All Photos"}
                return await self.async_step_albums()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_albums(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle album selection."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._title,
                data={
                    CONF_HOST: self._host,
                    CONF_API_KEY: self._api_key,
                    CONF_ALBUMS: user_input.get(CONF_ALBUMS, ["__favorites__"]),
                },
            )

        return self.async_show_form(
            step_id="albums",
            data_schema=vol.Schema({
                vol.Required(CONF_ALBUMS, default=["__favorites__"]): cv.multi_select(self._album_map),
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return ImmichPhotosOptionsFlow(config_entry)


class ImmichPhotosOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        hub = ImmichHub(
            host=self.config_entry.data[CONF_HOST],
            api_key=self.config_entry.data[CONF_API_KEY],
        )
        try:
            albums = await hub.list_all_albums()
            album_map = {"__favorites__": "Favorites", "__all__": "All Photos"}
            album_map.update({a["id"]: a["albumName"] for a in albums})
        except Exception:
            album_map = {"__favorites__": "Favorites", "__all__": "All Photos"}

        current = self.config_entry.options.get(
            CONF_ALBUMS, self.config_entry.data.get(CONF_ALBUMS, ["__favorites__"])
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_ALBUMS, default=current): cv.multi_select(album_map),
            }),
        )
