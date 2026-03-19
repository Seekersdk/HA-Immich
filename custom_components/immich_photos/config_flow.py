"""Config flow for Immich Photos integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

DOMAIN = "immich_photos"
CONF_HOST = "host"
CONF_API_KEY = "api_key"
CONF_ALBUMS = "albums"


class ImmichPhotosConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Immich Photos."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        _LOGGER.warning("[ImmichPhotos] async_step_user called, user_input=%s", user_input is not None)

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if not host.startswith(("http://", "https://")):
                host = "http://" + host
            host = host.rstrip("/")

            _LOGGER.warning("[ImmichPhotos] Saving entry for host: %s", host)

            return self.async_create_entry(
                title=f"Immich ({host})",
                data={
                    CONF_HOST: host,
                    CONF_API_KEY: user_input[CONF_API_KEY].strip(),
                    CONF_ALBUMS: ["__favorites__"],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_API_KEY): str,
            }),
        )
