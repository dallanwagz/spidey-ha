"""Config-flow tests (target: 100% path coverage).

Requires pytest-homeassistant-custom-component + HA test harness.
"""
from unittest.mock import patch

import pytest

pytest.importorskip("homeassistant")  # skip unless the HA test harness is installed

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import SOURCE_BLUETOOTH, SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResultType

from custom_components.sphero_spiderman.const import DOMAIN

ADDRESS = "AA:BB:CC:DD:EE:FF"

SERVICE_INFO = BluetoothServiceInfoBleak(
    name="ST8eab6d",
    address=ADDRESS,
    rssi=-45,
    manufacturer_data={},
    service_data={},
    service_uuids=[],
    source="local",
    device=None,
    advertisement=None,
    connectable=True,
    time=0,
    tx_power=-127,
)


async def _no_setup():
    return patch(
        "custom_components.sphero_spiderman.async_setup_entry", return_value=True
    )


async def test_bluetooth_discovery_confirm_creates_entry(hass):
    """A discovered figure can be confirmed and creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=SERVICE_INFO
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with await _no_setup():
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ST8eab6d"
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
    assert result["result"].unique_id == ADDRESS


async def test_bluetooth_discovery_already_configured(hass):
    """A second discovery of the same address aborts."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, data={CONF_ADDRESS: ADDRESS}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=SERVICE_INFO
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_no_devices(hass):
    """Manual flow with nothing nearby aborts."""
    with patch(
        "custom_components.sphero_spiderman.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_selects_device(hass):
    """Manual flow lists ST* devices and creates an entry on selection."""
    with patch(
        "custom_components.sphero_spiderman.config_flow.async_discovered_service_info",
        return_value=[SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        with await _no_setup():
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_ADDRESS: ADDRESS}
            )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ADDRESS: ADDRESS}
