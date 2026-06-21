"""Volume control (CHANGE_VOLUME) as a Number entity.

NOTE: write is not yet hardware-verified (the live unit confirmed status reads but no action was
visibly confirmed). The firmware handler reads {"VOL": <float 0.0-1.0>} (com.smarttoy.embedded.b.c).
"""
from __future__ import annotations

import json

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SpheroConfigEntry
from . import protocol as P
from .entity import SpheroEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpheroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the volume number entity."""
    async_add_entities([SpheroVolume(entry.runtime_data.coordinator)])


class SpheroVolume(SpheroEntity, NumberEntity):
    """Figure volume, 0-100% (maps to the toy's 0.0-1.0 VOL field)."""

    _attr_translation_key = "volume"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 5
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_volume_set"

    @property
    def native_value(self) -> int | None:
        state = self.coordinator.data
        return None if state is None else state.volume

    async def async_set_native_value(self, value: float) -> None:
        dt = json.dumps({"VOL": round(value) / 100.0}, separators=(",", ":"))
        await self.coordinator.async_send(P.Op.CHANGE_VOLUME, dt)
