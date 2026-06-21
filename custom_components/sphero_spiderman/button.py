"""Button entities: one per fire-and-forget command."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Set up a button per simple command."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        SpheroCommandButton(coordinator, key, op)
        for key, op in P.SIMPLE_COMMANDS.items()
    )


class SpheroCommandButton(SpheroEntity, ButtonEntity):
    """A button that fires one figure command."""

    def __init__(self, coordinator, key: str, op: P.Op) -> None:
        super().__init__(coordinator)
        self._op = op
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.address}_{key}"

    async def async_press(self) -> None:
        await self.coordinator.async_send(self._op)
