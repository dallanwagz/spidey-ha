"""Integration services: send_command (any op) and connect_wifi (BLE WiFi provisioning)."""
from __future__ import annotations

import json

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from . import protocol as P
from .const import DOMAIN

SERVICE_SEND_COMMAND = "send_command"
SERVICE_CONNECT_WIFI = "connect_wifi"

SEND_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required("command"): vol.In(sorted(P.Op.__members__)),
        vol.Optional("data", default=""): cv.string,
    }
)

CONNECT_WIFI_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required("ssid"): cv.string,
        vol.Optional("password", default=""): cv.string,
    }
)


def _coordinator_for(hass: HomeAssistant, device_id: str):
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise HomeAssistantError("Unknown device")
    address = next((i[1] for i in device.identifiers if i[0] == DOMAIN), None)
    if address is None:
        raise HomeAssistantError("Device is not a Sphero Spider-Man figure")
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry and entry.domain == DOMAIN and entry.unique_id == address:
            return entry.runtime_data.coordinator
    raise HomeAssistantError("No loaded entry for that device")


def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
        return

    async def _handle_send_command(call: ServiceCall) -> None:
        coordinator = _coordinator_for(hass, call.data[CONF_DEVICE_ID])
        await coordinator.async_send(P.Op[call.data["command"]], call.data["data"])

    async def _handle_connect_wifi(call: ServiceCall) -> None:
        coordinator = _coordinator_for(hass, call.data[CONF_DEVICE_ID])
        dt = json.dumps(
            {"SSID": call.data["ssid"], "PWD": call.data["password"]},
            separators=(",", ":"),
        )
        await coordinator.async_send(P.Op.CONNECT_TO_SSID, dt)

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_COMMAND, _handle_send_command, schema=SEND_COMMAND_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CONNECT_WIFI, _handle_connect_wifi, schema=CONNECT_WIFI_SCHEMA
    )
