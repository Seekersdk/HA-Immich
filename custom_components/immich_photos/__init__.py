"""Immich Photos integration for Home Assistant."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ImmichApiClient, ImmichConnectionError, ImmichAuthError
from .const import (
    DOMAIN,
    CONF_HOST,
    CONF_API_KEY,
    CONF_ALBUMS,
    ALBUM_ID_FAVORITES,
    ALBUM_VIRTUAL,
    UPDATE_INTERVAL_MAP,
    DEFAULT_UPDATE_INTERVAL,
)
from .coordinator import ImmichAlbumCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera", "sensor", "select"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Immich Photos from a config entry."""
    host = entry.data[CONF_HOST]
    api_key = entry.data[CONF_API_KEY]

    session = async_get_clientsession(hass)
    client = ImmichApiClient(host, api_key, session)

    try:
        await client.validate()
    except ImmichAuthError as err:
        _LOGGER.error("Invalid Immich API key: %s", err)
        return False
    except ImmichConnectionError as err:
        raise ConfigEntryNotReady(f"Cannot connect to Immich at {host}: {err}") from err

    # Build album name map
    try:
        real_albums = await client.get_albums()
        album_name_map: dict[str, str] = {**ALBUM_VIRTUAL}
        for a in real_albums:
            album_name_map[a.id] = a.name
    except Exception as err:
        _LOGGER.warning("Could not fetch album list: %s", err)
        album_name_map = {**ALBUM_VIRTUAL}

    # Determine configured albums (options override data)
    selected_albums: list[str] = entry.options.get(
        CONF_ALBUMS, entry.data.get(CONF_ALBUMS, [ALBUM_ID_FAVORITES])
    )

    default_interval_seconds = UPDATE_INTERVAL_MAP[DEFAULT_UPDATE_INTERVAL]

    coordinators: dict[str, ImmichAlbumCoordinator] = {}
    for album_id in selected_albums:
        name = album_name_map.get(album_id, album_id)
        coordinator = ImmichAlbumCoordinator(
            hass=hass,
            client=client,
            album_id=album_id,
            album_name=name,
            update_interval_seconds=default_interval_seconds,
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators[album_id] = coordinator

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinators": coordinators,
        "album_name_map": album_name_map,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (idempotent)
    _register_services(hass)

    # Reload when options change
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _all_coordinators(hass: HomeAssistant) -> list[ImmichAlbumCoordinator]:
    result = []
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if isinstance(entry_data, dict):
            result.extend(entry_data.get("coordinators", {}).values())
    return result


def _coordinators_for_entities(
    hass: HomeAssistant, entity_ids: list[str]
) -> list[ImmichAlbumCoordinator]:
    """Return coordinators whose camera entity_id matches one of the given ids."""
    matched = []
    for coordinator in _all_coordinators(hass):
        slug = _slugify(coordinator.album_name)
        candidate_ids = {
            f"camera.{slug}_media",
            f"camera.immich_{slug}_media",
            f"camera.immich_photos_{slug}_media",
            f"camera.immich_photos_{_slugify(coordinator.album_id)}_media",
        }
        if candidate_ids & set(entity_ids):
            matched.append(coordinator)
    return matched


def _register_services(hass: HomeAssistant) -> None:
    """Register integration-level services (safe to call multiple times)."""

    if hass.services.has_service(DOMAIN, "next_media"):
        return  # Already registered

    async def handle_next_media(call: ServiceCall) -> None:
        entity_ids: list[str] = call.data.get("entity_id", [])
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        mode: str | None = call.data.get("mode")

        coordinators = (
            _coordinators_for_entities(hass, entity_ids)
            if entity_ids
            else _all_coordinators(hass)
        )
        for coordinator in coordinators:
            await coordinator.async_next_media(mode=mode)

    async def handle_next_media_all(call: ServiceCall) -> None:
        mode: str | None = call.data.get("mode")
        for coordinator in _all_coordinators(hass):
            await coordinator.async_next_media(mode=mode)

    async def handle_set_date_filter(call: ServiceCall) -> None:
        entity_ids: list[str] = call.data.get("entity_id", [])
        if isinstance(entity_ids, str):
            entity_ids = [entity_ids]
        filter_mode: str = call.data.get("filter_mode", "None")
        after = _parse_dt(call.data.get("after"))
        before = _parse_dt(call.data.get("before"))

        coordinators = (
            _coordinators_for_entities(hass, entity_ids)
            if entity_ids
            else _all_coordinators(hass)
        )
        for coordinator in coordinators:
            coordinator.date_filter_mode = filter_mode
            coordinator.date_filter_after = after
            coordinator.date_filter_before = before
            await coordinator.async_force_refresh_pool()
            await coordinator.async_next_media()

    hass.services.async_register(DOMAIN, "next_media", handle_next_media)
    hass.services.async_register(DOMAIN, "next_media_all", handle_next_media_all)
    hass.services.async_register(DOMAIN, "set_date_filter", handle_set_date_filter)
