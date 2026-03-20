"""Select entities for Immich Photos."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    IMAGE_SELECTION_MODES,
    CROP_MODES,
    UPDATE_INTERVALS,
    UPDATE_INTERVAL_MAP,
    DEFAULT_UPDATE_INTERVAL,
)
from .coordinator import ImmichAlbumCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: dict[str, ImmichAlbumCoordinator] = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    entities = []
    for coordinator in coordinators.values():
        entities.append(ImmichSelectionModeSelect(coordinator, entry))
        entities.append(ImmichCropModeSelect(coordinator, entry))
        entities.append(ImmichUpdateIntervalSelect(coordinator, entry))
    async_add_entities(entities)


class _ImmichBaseSelect(CoordinatorEntity[ImmichAlbumCoordinator], SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ImmichAlbumCoordinator, entry: ConfigEntry, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{coordinator.album_id}_{key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_{self.coordinator.album_id}")},
            "name": f"Immich – {self.coordinator.album_name}",
            "manufacturer": "Immich",
            "model": "Photo Frame",
        }


class ImmichSelectionModeSelect(_ImmichBaseSelect):
    _attr_options = IMAGE_SELECTION_MODES
    _attr_icon = "mdi:shuffle-variant"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "selection_mode", "Image Selection Mode")

    @property
    def current_option(self) -> str:
        return self.coordinator.selection_mode

    async def async_select_option(self, option: str) -> None:
        self.coordinator.selection_mode = option
        self.async_write_ha_state()


class ImmichCropModeSelect(_ImmichBaseSelect):
    _attr_options = CROP_MODES
    _attr_icon = "mdi:crop"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "crop_mode", "Crop Mode")

    @property
    def current_option(self) -> str:
        return self.coordinator.crop_mode

    async def async_select_option(self, option: str) -> None:
        self.coordinator.crop_mode = option
        await self.coordinator.async_next_media()
        self.async_write_ha_state()


class ImmichUpdateIntervalSelect(_ImmichBaseSelect):
    _attr_options = UPDATE_INTERVALS
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "update_interval", "Update Interval")
        self._current = DEFAULT_UPDATE_INTERVAL

    @property
    def current_option(self) -> str:
        return self._current

    async def async_select_option(self, option: str) -> None:
        self._current = option
        seconds = UPDATE_INTERVAL_MAP.get(option, 300)
        from datetime import timedelta
        self.coordinator.update_interval = timedelta(seconds=seconds)
        self.async_write_ha_state()
