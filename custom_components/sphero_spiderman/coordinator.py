"""BLE connection coordinator for the Sphero Spider-Man figure."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import protocol as P
from .const import DOMAIN, RECONNECT_BACKOFF_MAX, RECONNECT_BACKOFF_MIN, STALE_AFTER

_LOGGER = logging.getLogger(__name__)


class SpheroSpidermanCoordinator(DataUpdateCoordinator[P.ToyState]):
    """Owns the BLE link: connect, subscribe to notify, decode frames, reconnect.

    Push-based (local_push): frames arrive via notify and we publish state immediately.
    A staleness watchdog tears down and reconnects if the link is up but frames stop.
    """

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        super().__init__(hass, _LOGGER, name=name)
        self.address = address
        self._client: BleakClient | None = None
        self._reassembler = P.Reassembler()
        self._state = P.ToyState()
        self._run_task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._last_frame = 0.0
        self._write_lock = asyncio.Lock()

    # ---- lifecycle -------------------------------------------------------
    async def async_start(self) -> None:
        self._stop.clear()
        self._run_task = self.hass.async_create_background_task(
            self._run(), f"{DOMAIN}-{self.address}-conn"
        )

    async def async_stop(self) -> None:
        self._stop.set()
        if self._run_task:
            self._run_task.cancel()
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    # ---- connection loop -------------------------------------------------
    def _find_device(self) -> BLEDevice | None:
        """Find the figure's current connectable BLEDevice.

        The figure advertises under a ROTATING resolvable-private-address, so a fixed
        configured address goes stale. Try the configured address first, then fall back to
        matching the advertised name among currently-seen connectable devices, updating
        self.address to whatever it's using now.
        """
        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is not None:
            return device
        for si in bluetooth.async_discovered_service_info(self.hass, connectable=True):
            if si.name and (si.name == self.name or si.name.startswith("ST")):
                if si.address != self.address:
                    _LOGGER.warning(
                        "%s now advertising as %s (rotated address); using it",
                        self.name, si.address,
                    )
                    self.address = si.address
                return si.device
        return None

    async def _run(self) -> None:
        backoff = RECONNECT_BACKOFF_MIN
        while not self._stop.is_set():
            device = self._find_device()
            if device is None:
                _LOGGER.warning(
                    "%s: no CONNECTABLE device seen for it yet (need an ESPHome proxy with "
                    "active connections in range, or it isn't advertising); waiting", self.name
                )
                await self._sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX)
                continue
            try:
                _LOGGER.warning("%s: connecting to %s …", self.name, device.address)
                await self._connect_and_serve(device)
                backoff = RECONNECT_BACKOFF_MIN
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("%s: connection cycle failed: %r", self.name, err)
                await self._sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX)

    async def _connect_and_serve(self, device: BLEDevice) -> None:
        client = await establish_connection(BleakClient, device, self.address)
        self._client = client
        try:
            # Status arrives on CHAR_NOTIFY (740563D5); each chunk must be ack'd by writing to
            # CHAR_ACK (1EAEBABD) for the toy to send the next one (its flow control).
            await client.start_notify(P.CHAR_NOTIFY, self._on_notify)
            self._last_frame = time.monotonic()
            # Onboard first: the toy gates action ops behind a BLE login. Verified live that
            # LOGIN + GET_SETUP_STATE clears the setup gate so ATTACK/etc. are accepted.
            await self._onboard()
            # Prime the toy with info/battery queries.
            await self.async_send(P.Op.GET_TOY_INFO)
            await self.async_send(P.Op.GET_BATTERY_STATUS)
            await self._watchdog(client)
        finally:
            self._client = None
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    async def _watchdog(self, client: BleakClient) -> None:
        """Hold the connection; reconnect if frames go stale."""
        while not self._stop.is_set() and client.is_connected:
            await self._sleep(15.0)
            if time.monotonic() - self._last_frame > STALE_AFTER:
                _LOGGER.debug("no frames for %ss; reconnecting", STALE_AFTER)
                return

    # ---- io --------------------------------------------------------------
    @callback
    def _on_notify(self, _char, data: bytearray) -> None:
        self._last_frame = time.monotonic()
        # Ack this chunk so the toy releases the next one (POST_NOTIFICATION flow control).
        if self._client is not None:
            self.hass.async_create_task(self._ack())
        msg = self._reassembler.feed(bytes(data))
        if msg is None:
            return
        if msg.get("_op") == P.Op.SPIDER_BUTTON_SHORT_PRESS:
            self._state.last_button_press = time.time()
        P.apply_to_state(self._state, msg)
        self.async_set_updated_data(self._state)

    async def _ack(self) -> None:
        client = self._client
        if client is None or not client.is_connected:
            return
        try:
            await client.write_gatt_char(P.CHAR_ACK, P.ACK_VALUE, response=True)
        except Exception:  # noqa: BLE001
            pass

    async def _onboard(self) -> None:
        """Run the BLE login handshake so the toy accepts action commands.

        Verified live: LOGIN with the bundled creds + GET_SETUP_STATE clears the setup gate.
        Best-effort — a failure here shouldn't kill the connection (reads still work).
        """
        try:
            await self.async_send(
                P.Op.LOGIN,
                json.dumps({"USR": P.LOGIN_USER, "UPW": P.LOGIN_PASS}, separators=(",", ":")),
            )
            await self._sleep(1.5)
            await self.async_send(P.Op.GET_SETUP_STATE)
            await self._sleep(0.5)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("onboarding handshake failed (continuing): %s", err)

    async def async_send(self, op: P.Op | int, dt: str = "") -> None:
        """Frame and write a command to the figure (commands go to CHAR_WRITE = 81E4C615)."""
        client = self._client
        if client is None or not client.is_connected:
            raise RuntimeError("not connected")
        async with self._write_lock:
            for chunk in P.frame_command(op, dt):
                await client.write_gatt_char(P.CHAR_WRITE, chunk, response=True)
                await asyncio.sleep(0.03)

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    def add_update_listener(self, cb: Callable[[], None]):  # convenience
        return self.async_add_listener(cb)
