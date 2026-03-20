"""Sensor entities for Immich Frame."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN

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
        sensors = [
            ImmichFilenameSensor(album_state, entry_id),
            ImmichDatetimeSensor(album_state, entry_id),
            ImmichPoolSizeSensor(album_state, entry_id),
        ]
        album_state.sensor_entities.extend(sensors)
        entities.extend(sensors)

    async_add_entities(entities)


class _ImmichSensorBase(SensorEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, album_state, entry_id: str) -> None:
        self._album_state = album_state
        self._entry_id = entry_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry_id}_{self._album_state.album_id}")},
            name=f"Immich \u2013 {self._album_state.album_name}",
            manufacturer="Immich",
            model="Photo Frame",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state not in (None, "unknown", "unavailable"):
            self._restore_state(last.state)

    def _restore_state(self, state: str) -> None:
        pass


class ImmichFilenameSensor(_ImmichSensorBase):
    _attr_name = "Current Filename"
    _attr_icon = "mdi:file-image-outline"

    def __init__(self, album_state, entry_id):
        super().__init__(album_state, entry_id)
        self._attr_unique_id = f"{entry_id}_{album_state.album_id}_filename"

    @property
    def native_value(self) -> str:
        return self._album_state.current_filename or None


class ImmichDatetimeSensor(_ImmichSensorBase):
    _attr_name = "Photo Taken"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, album_state, entry_id):
        super().__init__(album_state, entry_id)
        self._attr_unique_id = f"{entry_id}_{album_state.album_id}_datetime"

    @property
    def native_value(self) -> str:
        return self._album_state.current_datetime or None


class ImmichPoolSizeSensor(_ImmichSensorBase):
    _attr_name = "Pool Size"
    _attr_icon = "mdi:image-multiple-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "photos"

    def __init__(self, album_state, entry_id):
        super().__init__(album_state, entry_id)
        self._attr_unique_id = f"{entry_id}_{album_state.album_id}_pool_size"

    @property
    def native_value(self) -> int | None:
        return self._album_state.pool_count or None
