"""Camera entity for Immich Photos."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ATTR_MEDIA_ID, ATTR_FILENAME, ATTR_CREATION_TIMESTAMP, ATTR_MEDIA_COUNT, ATTR_IS_UPDATING
from .coordinator import ImmichAlbumCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Immich Photos camera entities."""
    coordinators: dict[str, ImmichAlbumCoordinator] = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    entities = [
        ImmichPhotoCamera(coordinator, entry)
        for coordinator in coordinators.values()
    ]
    async_add_entities(entities)


class ImmichPhotoCamera(CoordinatorEntity[ImmichAlbumCoordinator], Camera):
    """Camera entity that streams current Immich photo."""

    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature(0)

    def __init__(self, coordinator: ImmichAlbumCoordinator, entry: ConfigEntry) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{coordinator.album_id}_camera"
        self._attr_name = f"{coordinator.album_name} Media"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_{self.coordinator.album_id}")},
            "name": f"Immich – {self.coordinator.album_name}",
            "manufacturer": "Immich",
            "model": "Photo Frame",
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            ATTR_MEDIA_ID: data.get("media_id"),
            ATTR_FILENAME: data.get("filename"),
            ATTR_CREATION_TIMESTAMP: data.get("creation_timestamp"),
            ATTR_MEDIA_COUNT: data.get("media_count", 0),
            ATTR_IS_UPDATING: data.get("is_updating", False),
        }

    @property
    def is_recording(self) -> bool:
        return False

    @property
    def is_streaming(self) -> bool:
        return False

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the current camera image bytes."""
        return self.coordinator.current_image_bytes
