# Sphero Spider-Man — Home Assistant integration

Local control of the **Sphero "Spider-Man Interactive App-Enabled Super Hero"** figure over
Bluetooth LE — no cloud, no vendor app (Sphero's `smarttoy.org` servers are dead).

> **Your figure has to be alive first.** Because the vendor cloud is gone, many of these toys are
> stuck/bricked at setup. If yours is, revive it with **[spidey-jailbreak](https://github.com/dallanwagz/spidey-jailbreak)**
> (sinkhole the dead domain → local mock → re-signed OTA), then come back here for Home Assistant control.

> **Status: protocol fully reverse-engineered and LIVE-VERIFIED on hardware — reads *and* actions.**
> The XOR key (`$u?4dMk?ii/;b0g`), framing, and characteristic roles are confirmed: the live unit
> returns correct `INFO`/`BATTERY_STATUS`/`SETUP_STATUS` frames (battery %, charging, WiFi, volume),
> **and** action commands fire — after the BLE login handshake, `ATTACK` produced a visible/audible
> interactive attack sequence. Golden frames are in the test suite.
>
> Characteristic roles (verified live): **write commands → `81E4C615`**, **status notify ←
> `740563D5`**, **ack each notify chunk → `1EAEBABD`** (`\x01`).

## What works
- **BLE, local push.** Auto-discovers the figure (it advertises a name starting `ST…`).
- **Sensors:** Battery %, Volume, Firmware (diagnostic); **Charging** binary sensor.
- **Buttons:** **Attack** (verified), **Beep**, **Start play**, **Sleep**.
- **Volume number:** sets `CHANGE_VOLUME`.
- **Eye expression (optional, SSH):** a `select` to drive the eye animations — requires a rooted
  figure; see below.
- **Services:** `sphero_spiderman.send_command` (fire any of the ~113 ops) and
  `sphero_spiderman.connect_wifi` (provision WiFi over BLE).

On connect the integration runs a short **login handshake** (`LOGIN` + `GET_SETUP_STATE`) that clears
the figure's setup gate so action commands are accepted.

## Requirements
- A **Bluetooth host that can do BLE notifications with this device's non-standard GATT** — i.e.
  Linux/BlueZ (the HA host's own adapter, a USB dongle) or an **ESPHome/Shelly Bluetooth proxy**
  near the figure. (macOS CoreBluetooth cannot; see the note below.) The figure advertises weakly,
  so keep the proxy/adapter within a few metres.
- Home Assistant 2024.8 or newer.

## Install (HACS)
1. HACS → ⋮ → **Custom repositories** → add this repo, category **Integration**.
2. Install **Sphero Spider-Man**, restart HA.
3. The figure should be auto-discovered (**Settings → Devices & Services**). Otherwise **+ Add
   Integration → Sphero Spider-Man** and pick it from the list. Keep the vendor app closed — the
   figure accepts a single BLE connection.

## Advertising / reconnect
The figure only advertises (`ST…`) for a window after its toy app (re)starts, and stops once a
central is connected. For the **initial** connect — or to recover if the link drops — kick it back
into advertising: a short press of the chest button works, or (on a rooted figure) the
`spidey_advertise.sh` helper from **[spidey-jailbreak](https://github.com/dallanwagz/spidey-jailbreak)**.
Once HA connects it holds the link, so this isn't needed continuously.

## Eye expressions (optional, root/SSH)
The eyes are a Tenx animation co-processor on I²C, **not** on the BLE path — they're driven by
writing opcodes to `/sys/class/dsp/dsp_reg` as root. On a rooted figure (dropbear on `:2222`, set up
via spidey-jailbreak), enable the **Eye expression** select:

**Settings → Devices & Services → Sphero Spider-Man → Configure**, then set the **SSH private key
path** (a key HA can read whose public half is in the figure's `authorized_keys`), and optionally the
host/port/user. Leave the key blank to disable. This control is intentionally kept **separate from the
BLE core** (which targets HA Core) because it requires a root shell on the device.

## How it works (protocol, briefly)
Frames are `#MS` + `base64(XOR(json, key))` (20-byte chunks) + `#ME` written to the command char
`81E4C615…`; status arrives as the same framing on notify char `740563D5…`, and each inbound chunk is
ack'd by writing to `1EAEBABD…`. JSON is `{"OP":<op>,"DT":<data>,"ID":…,"ACC":…}`. The full
reverse-engineering write-up lives in the jailbreak repo's `FINDINGS.md`; the pure, unit-tested logic
is `custom_components/sphero_spiderman/protocol.py`.

### Note: non-standard notifications
The figure's notify characteristics have **no standard `0x2902` CCCD**. BlueZ and Android enable
notifications fine; **macOS CoreBluetooth cannot**, so a Mac-hosted HA/dev box won't receive status
(commands still send). Use a Linux BLE host or an ESPHome proxy.

## Development
```bash
python -m pytest tests/test_protocol.py        # pure protocol + golden-frame tests (no HA needed)
# Full suite (config-flow) needs: pip install pytest-homeassistant-custom-component  (Python <= 3.13)
ruff check custom_components tests
```

## Path to Home Assistant Core
The **BLE** integration is built to Core standard. To upstream: delete `hacs.json` + the
`manifest.json` `version` field, move `custom_components/sphero_spiderman/` →
`homeassistant/components/`, and open the code + docs + brands PRs. The optional **eye-expression**
select uses SSH (`asyncssh`) + a root shell on the device, so it would be dropped from a Core submission.

## Credits
Reverse-engineered with the `untether` methodology. Companion: the
**[spidey-jailbreak](https://github.com/dallanwagz/spidey-jailbreak)** revival toolkit. Not affiliated
with Sphero, Hasbro, or Marvel.
