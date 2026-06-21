"""Binary sensors for Sphero Spider-Man."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SpheroConfigEntry
from .entity import SpheroEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpheroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    async_add_entities([SpheroChargingSensor(entry.runtime_data.coordinator)])


class SpheroChargingSensor(SpheroEntity, BinarySensorEntity):
    """Charging state, decoded from the BATTERY_STATUS CHG flag."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "charging"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_charging"

    @property
    def is_on(self) -> bool | None:
        state = self.coordinator.data
        return None if state is None else state.charging
