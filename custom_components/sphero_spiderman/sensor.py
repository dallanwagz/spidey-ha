"""Sensor entities for Sphero Spider-Man."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SpheroConfigEntry
from . import protocol as P
from .entity import SpheroEntity


@dataclass(frozen=True, kw_only=True)
class SpheroSensorDescription(SensorEntityDescription):
    """Describes a Sphero sensor and how to read it from ToyState."""

    value_fn: Callable[[P.ToyState], int | str | None]


SENSORS: tuple[SpheroSensorDescription, ...] = (
    SpheroSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.battery_percent,
    ),
    SpheroSensorDescription(
        key="volume",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.volume,
    ),
    SpheroSensorDescription(
        key="firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.firmware,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpheroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(SpheroSensor(coordinator, d) for d in SENSORS)


class SpheroSensor(SpheroEntity, SensorEntity):
    """A decoded status field exposed as a sensor."""

    entity_description: SpheroSensorDescription

    def __init__(self, coordinator, description: SpheroSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{coordinator.address}_{description.key}"

    @property
    def native_value(self) -> int | str | None:
        state = self.coordinator.data
        if state is None:
            return None
        return self.entity_description.value_fn(state)
