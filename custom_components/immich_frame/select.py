"""Select entities for Immich Frame."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    entry_state = data["state"]
    entry_id = config_entry.entry_id

    async_add_entities([
        ImmichCropModeSelect(entry_state, entry_id, hass),
        ImmichSelectionModeSelect(entry_state, entry_id, hass),
        ImmichUpdateIntervalSelect(entry_state, entry_id, hass),
    ])


class _ImmichSelectBase(SelectEntity, RestoreEntity):
    """Base select entity with state restore."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry_state: Any, entry_id: str, hass: HomeAssistant) -> None:
        self._entry_state = entry_state
        self._entry_id = entry_id
        self.hass = hass

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state in self._attr_options:
            await self.async_select_option(last.state)

    def _refresh_image_entities(self) -> None:
        """Force immediate refresh on all image entities."""
        data = self.hass.data.get(DOMAIN, {}).get(self._entry_id, {})
        for entity in data.get("image_entities", []):
            entity._last_image_load = None
            entity.async_schedule_update_ha_state(force_refresh=True)


class ImmichCropModeSelect(_ImmichSelectBase):
    _attr_options = CROP_MODES
    _attr_icon = "mdi:crop"
    _attr_unique_id = None

    def __init__(self, entry_state, entry_id, hass):
        super().__init__(entry_state, entry_id, hass)
        self._attr_unique_id = f"{entry_id}_crop_mode"
        self._attr_name = "Crop Mode"
        self._attr_current_option = DEFAULT_CROP_MODE

    async def async_select_option(self, option: str) -> None:
        self._entry_state.crop_mode = option
        self._attr_current_option = option
        self.async_write_ha_state()
        self._refresh_image_entities()


class ImmichSelectionModeSelect(_ImmichSelectBase):
    _attr_options = SELECTION_MODES
    _attr_icon = "mdi:shuffle-variant"

    def __init__(self, entry_state, entry_id, hass):
        super().__init__(entry_state, entry_id, hass)
        self._attr_unique_id = f"{entry_id}_selection_mode"
        self._attr_name = "Image Selection Mode"
        self._attr_current_option = DEFAULT_SELECTION_MODE

    async def async_select_option(self, option: str) -> None:
        self._entry_state.selection_mode = option
        self._attr_current_option = option
        self.async_write_ha_state()
        self._refresh_image_entities()


class ImmichUpdateIntervalSelect(_ImmichSelectBase):
    _attr_options = UPDATE_INTERVALS
    _attr_icon = "mdi:timer-outline"

    def __init__(self, entry_state, entry_id, hass):
        super().__init__(entry_state, entry_id, hass)
        self._attr_unique_id = f"{entry_id}_update_interval"
        self._attr_name = "Update Interval"
        self._attr_current_option = DEFAULT_UPDATE_INTERVAL

    async def async_select_option(self, option: str) -> None:
        self._entry_state.update_interval = option
        self._attr_current_option = option
        self.async_write_ha_state()
        # No image refresh needed — interval controls timing only
