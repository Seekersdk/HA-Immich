"""Sensor entities for Immich Photos."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ImmichAlbumCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinators: dict[str, ImmichAlbumCoordinator] = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    entities = []
    for coordinator in coordinators.values():
        entities.append(ImmichFilenameSensor(coordinator, entry))
        entities.append(ImmichTimestampSensor(coordinator, entry))
        entities.append(ImmichMediaCountSensor(coordinator, entry))
    async_add_entities(entities)


class _ImmichBaseSensor(CoordinatorEntity[ImmichAlbumCoordinator], SensorEntity):
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
            "name": f"Immich \u2013 {self.coordinator.album_name}",
            "manufacturer": "Immich",
            "model": "Photo Frame",
        }

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        return data.get(self._key)


class ImmichFilenameSensor(_ImmichBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "filename", "Filename")
        self._attr_icon = "mdi:file-image"


class ImmichTimestampSensor(_ImmichBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "creation_timestamp", "Creation Timestamp")
        self._attr_icon = "mdi:calendar"
        self._attr_device_class = "timestamp"


class ImmichMediaCountSensor(_ImmichBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "media_count", "Media Count")
        self._attr_icon = "mdi:image-multiple"
        self._attr_native_unit_of_measurement = "photos"
