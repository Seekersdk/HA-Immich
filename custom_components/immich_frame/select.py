"""Select entities for Immich Frame — one set per album."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    CROP_MODES, DEFAULT_CROP_MODE,
    SELECTION_MODES, DEFAULT_SELECTION_MODE,
    UPDATE_INTERVALS, DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    album_states: dict = data["album_states"]
    entry_id = config_entry.entry_id

    entities = []
    for album_state in album_states.values():
        entities += [
            ImmichCropModeSelect(album_state, entry_id),
            ImmichSelectionModeSelect(album_state, entry_id),
            ImmichUpdateIntervalSelect(album_state, entry_id),
        ]
    async_add_entities(entities)


class _ImmichSelectBase(SelectEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, album_state, entry_id: str) -> None:
        self._album_state = album_state
        self._entry_id = entry_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_{self._album_state.album_id}")},
            name=f"Immich – {self._album_state.album_name}",
            manufacturer="Immich",
            model="Photo Frame",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state in self._attr_options:
            await self.async_select_option(last.state)

    def _refresh_image_entities(self) -> None:
        for entity in self._album_state.image_entities:
            entity._last_image_load = None
            entity.async_schedule_update_ha_state(force_refresh=True)


class ImmichCropModeSelect(_ImmichSelectBase):
    _attr_options = CROP_MODES
    _attr_icon = "mdi:crop"
    _attr_name = "Crop Mode"

    def __init__(self, album_state, entry_id):
        super().__init__(album_state, entry_id)
        self._attr_unique_id = f"{entry_id}_{album_state.album_id}_crop_mode"
        self._attr_current_option = DEFAULT_CROP_MODE

    async def async_select_option(self, option: str) -> None:
        self._album_state.crop_mode = option
        self._attr_current_option = option
        self.async_write_ha_state()
        self._refresh_image_entities()


class ImmichSelectionModeSelect(_ImmichSelectBase):
    _attr_options = SELECTION_MODES
    _attr_icon = "mdi:shuffle-variant"
    _attr_name = "Image Selection Mode"

    def __init__(self, album_state, entry_id):
        super().__init__(album_state, entry_id)
        self._attr_unique_id = f"{entry_id}_{album_state.album_id}_selection_mode"
        self._attr_current_option = DEFAULT_SELECTION_MODE

    async def async_select_option(self, option: str) -> None:
        self._album_state.selection_mode = option
        self._attr_current_option = option
        self.async_write_ha_state()
        self._refresh_image_entities()


class ImmichUpdateIntervalSelect(_ImmichSelectBase):
    _attr_options = UPDATE_INTERVALS
    _attr_icon = "mdi:timer-outline"
    _attr_name = "Update Interval"

    def __init__(self, album_state, entry_id):
        super().__init__(album_state, entry_id)
        self._attr_unique_id = f"{entry_id}_{album_state.album_id}_update_interval"
        self._attr_current_option = DEFAULT_UPDATE_INTERVAL

    async def async_select_option(self, option: str) -> None:
        self._album_state.update_interval = option
        self._attr_current_option = option
        self.async_write_ha_state()
