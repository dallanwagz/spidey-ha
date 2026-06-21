"""The Sphero Spider-Man integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SpheroSpidermanCoordinator
from .services import async_register_services

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]


@dataclass
class SpheroData:
    """Runtime data stored on the config entry."""

    coordinator: SpheroSpidermanCoordinator


type SpheroConfigEntry = ConfigEntry[SpheroData]


async def async_setup_entry(hass: HomeAssistant, entry: SpheroConfigEntry) -> bool:
    """Set up Sphero Spider-Man from a config entry."""
    coordinator = SpheroSpidermanCoordinator(
        hass, address=entry.unique_id or entry.data["address"], name=entry.title
    )
    await coordinator.async_start()
    entry.runtime_data = SpheroData(coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_register_services(hass)
    # Reload when options change so the eye-expression select appears/disappears.
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    return True


async def _async_reload_on_update(hass: HomeAssistant, entry: SpheroConfigEntry) -> None:
    """Reload the entry after its options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SpheroConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.coordinator.async_stop()
    return unload_ok
