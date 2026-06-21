"""Eye-expression Select — root/SSH bonus surface (independent of the BLE link).

Only created when an SSH key is configured in the entry options (CONF_EYE_KEY); otherwise
the platform adds nothing. See eyes.py for the protocol.
"""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SpheroConfigEntry, eyes
from .const import (
    CONF_EYE_HOST,
    CONF_EYE_KEY,
    CONF_EYE_PORT,
    CONF_EYE_USER,
    DEFAULT_EYE_HOST,
    DEFAULT_EYE_PORT,
    DEFAULT_EYE_USER,
)
from .entity import SpheroEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpheroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the eye-expression select, but only if SSH eye control is configured."""
    key = entry.options.get(CONF_EYE_KEY)
    host = entry.options.get(CONF_EYE_HOST, DEFAULT_EYE_HOST)
    if not key or not host:
        return
    coordinator = entry.runtime_data.coordinator
    ssh_cfg = {
        "host": host,
        "port": entry.options.get(CONF_EYE_PORT, DEFAULT_EYE_PORT),
        "username": entry.options.get(CONF_EYE_USER, DEFAULT_EYE_USER),
        "client_keys": [key],
    }
    async_add_entities([EyeExpressionSelect(coordinator, ssh_cfg)])


class EyeExpressionSelect(SpheroEntity, SelectEntity):
    """Pick a canned eye expression (driven over SSH, not BLE)."""

    _attr_translation_key = "eye_expression"
    _attr_options = list(eyes.EYE_EXPRESSIONS)

    def __init__(self, coordinator, ssh_cfg: dict) -> None:
        super().__init__(coordinator)
        self._ssh = ssh_cfg
        self._attr_unique_id = f"{coordinator.address}_eye_expression"
        self._attr_current_option = None

    @property
    def available(self) -> bool:
        # SSH transport is independent of the BLE link, so don't gate on it.
        return True

    async def async_select_option(self, option: str) -> None:
        await eyes.async_set_expression(option, **self._ssh)
        self._attr_current_option = option
        self.async_write_ha_state()
