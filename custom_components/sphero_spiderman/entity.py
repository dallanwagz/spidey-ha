"""Base entity for Sphero Spider-Man."""
from __future__ import annotations

from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SpheroSpidermanCoordinator


class SpheroEntity(CoordinatorEntity[SpheroSpidermanCoordinator]):
    """Common base: device info + availability tied to the BLE link."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SpheroSpidermanCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            connections={("bluetooth", coordinator.address)},
            identifiers={(DOMAIN, coordinator.address)},
            manufacturer="Sphero",
            model="Spider-Man Interactive Super Hero",
            name=coordinator.name,
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.connected
