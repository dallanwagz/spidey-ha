"""Config flow for Sphero Spider-Man."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback

from .const import (
    CONF_EYE_HOST,
    CONF_EYE_KEY,
    CONF_EYE_PORT,
    CONF_EYE_USER,
    DEFAULT_EYE_HOST,
    DEFAULT_EYE_PORT,
    DEFAULT_EYE_USER,
    DOMAIN,
    NAME_PREFIX,
)


class SpheroSpidermanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Sphero Spider-Man figure."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, str] = {}  # address -> title

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options: configure the (optional) SSH eye-expression control."""
        return SpheroOptionsFlow()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a flow initialized by Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        title = discovery_info.name or discovery_info.address
        self._discovered = {discovery_info.address: title}
        self.context["title_placeholders"] = {"name": title}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a single discovered device."""
        address = next(iter(self._discovered))
        title = self._discovered[address]
        if user_input is not None:
            return self.async_create_entry(title=title, data={CONF_ADDRESS: address})
        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm", description_placeholders={"name": title}
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup: pick from nearby ST* devices."""
        from homeassistant.components.bluetooth import async_discovered_service_info

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered.get(address, address),
                data={CONF_ADDRESS: address},
            )

        current = self._async_current_ids()
        choices: dict[str, str] = {}
        for info in async_discovered_service_info(self.hass):
            if (
                (info.name or "").startswith(NAME_PREFIX)
                and info.address not in current
            ):
                choices[info.address] = f"{info.name} ({info.address})"
        if not choices:
            return self.async_abort(reason="no_devices_found")
        self._discovered = {a: t.split(" (")[0] for a, t in choices.items()}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(choices)}),
        )


class SpheroOptionsFlow(OptionsFlow):
    """Configure the optional SSH-driven eye-expression control.

    Set a private-key path to enable the Eye expression select; leave it blank to disable.
    HA must be able to SSH-reach the figure (our resurrection runs dropbear on :2222).
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # Drop blanks so a cleared key disables the eye select platform.
            opts = {k: v for k, v in user_input.items() if v not in (None, "")}
            return self.async_create_entry(title="", data=opts)

        cur = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(CONF_EYE_KEY, default=cur.get(CONF_EYE_KEY, "")): str,
                vol.Optional(
                    CONF_EYE_HOST, default=cur.get(CONF_EYE_HOST, DEFAULT_EYE_HOST)
                ): str,
                vol.Optional(
                    CONF_EYE_PORT, default=cur.get(CONF_EYE_PORT, DEFAULT_EYE_PORT)
                ): int,
                vol.Optional(
                    CONF_EYE_USER, default=cur.get(CONF_EYE_USER, DEFAULT_EYE_USER)
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
