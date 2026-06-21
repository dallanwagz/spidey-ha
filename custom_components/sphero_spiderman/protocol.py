"""Pure protocol logic for the Sphero Spider-Man interactive figure.

No Home Assistant imports — unit-tested against golden frames. Reverse-engineered from
the vendor APK (`com.sphero.spiderman` v1.1.5) and cross-validated against the toy's own
firmware (OTA `smarttoy_embedded_app`).

Wire format
-----------
Transport : BLE GATT. Toy = peripheral. Advertises *name only* (prefix "ST"), no service UUID.
Service   : 38A561E5-D18A-4C92-9F73-DBC0E5CD2E13
Write char: 81E4C615-... (central -> toy, commands)  [WRITE_CHARACTERISTIC_UUID]
Notify    : 740563D5-... (toy -> central, status)
Ack char  : 1EAEBABD-... (central -> toy; write ACK_VALUE after each notify chunk = flow control)
            ⚠ chars have NO standard 0x2902 CCCD; BlueZ/Android handle notify, macOS cannot.
            (Char roles + key + framing CONFIRMED live 2026-06-20 against the resurrected unit.)
Framing   : a message string is sent as separate GATT writes: "#MS", then <=20-char chunks, "#ME".
Payload   : the reassembled string is gs(json) = base64( json[i] XOR KEY[i % len] ), NO_WRAP.
JSON      : {"OP": <op ordinal>, "DT": <data>, "ID": <sender>, "ACC": <app meta>}
KEY       : 15-char static key recovered from libbazinga.so/libsecureconstants.so (see XOR_KEY).
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from enum import IntEnum

# ---- UUIDs ----------------------------------------------------------------
SERVICE_UUID = "38a561e5-d18a-4c92-9f73-dbc0e5cd2e13"
# Roles per the toy's GATT server (com.smarttoy.ble.a.b):
#   81E4C615 = WRITE_CHARACTERISTIC_UUID  -> central writes commands here
#   740563D5 = post/notify UUID           -> toy notifies status here
#   1EAEBABD = POST_NOTIFICATION_UUID      -> central writes an ack here after each notify chunk
CHAR_WRITE = "81e4c615-62f2-48b6-8be4-96dcd0801bb7"
CHAR_NOTIFY = "740563d5-3736-4033-87b5-029c38ccc893"
CHAR_ACK = "1eaebabd-4ce8-48c3-a1fc-fbe733e1e6ea"
ACK_VALUE = b"\x01"

MS = b"#MS"
ME = b"#ME"
CHUNK = 20

# ---- JSON keys (com.smarttoy.f / l) ---------------------------------------
K_TYPE, K_OP, K_DT, K_ID, K_ACC = "type", "OP", "DT", "ID", "ACC"

# 15-char XOR key, recovered by disassembling the native getSerialzedString/getAESKey
# (key[i] = table2[table1[i]] from static tables in the .so). Same on phone + toy.
XOR_KEY = b"$u?4dMk?ii/;b0g"

# ---- Operation catalog (com.smarttoy.f.b, ordinal = index) ----------------
_OPS = [
    "LOGIN", "SELECT_PROFILE", "PLAY_ACTIVITY", "GET_NETWORK_SSIDS", "CONNECT_TO_SSID", "QR_SETUP",
    "HANDSHAKE", "SLEEP_TOY", "PROCESS_UNLOCK_CODE", "REGISTER_ACCESS_TOKEN", "CHANGE_VOLUME",
    "GET_BATTERY_STATUS", "TEST_TOY", "TEST_TOY_EXTRACTION", "TEST_TOY_RECORDING", "PACK_COMPLETED",
    "INFO", "PROCESS_NETWORK_SSIDS", "SSID_CONNECTION_STATUS", "PARENT_INFO", "DISCONNECT_TOY",
    "PARENT_CONNECTED_TO_SOCKET", "PARENT_LOGOUT", "BATTERY_STATUS", "TEST_TOY_EXTRACTION_DONE",
    "TEST_TOY_RECORDING_DONE", "TEST_TOY_LED", "TEST_TOY_LED_DONE", "TEST_TOY_VOICE_RECOG",
    "TEST_TOY_VOICE_RECOG_DONE", "TEST_TOY_CARD_RECOG", "TEST_TOY_CARD_RECOG_DONE", "TEST_TOY_BURN_IN_MODE",
    "TEST_TOY_VOICE_RECOG_START", "TEST_TOY_NAME_TEST", "GET_API_TOKEN", "API_TOKEN", "TEST_TOY_INITIAL_DATA",
    "TEST_TOY_INITIAL_DATA_SENT", "PLAY_ACTIVITY_WITHOUT_ACC", "TEST_TOY_SILENCE_RECOG",
    "TEST_TOY_SILENCE_RECOG_DONE", "TEST_TOY_WIFI_STATUS_UPDATE", "TEST_TOY_SOCKETIO_CONNECT", "GET_TOY_INFO",
    "TOGGLE_VOLUME_CONTROL", "TEST_TOY_WIFI_STATUS", "TEST_TOY_IR_SENSOR", "TEST_TOY_IR_SENSOR_DONE",
    "TEST_TOY_DSP_SENSOR", "TEST_TOY_DSP_SENSOR_DONE", "TEST_TOY_G_SENSOR", "TEST_TOY_G_SENSOR_DONE",
    "TEST_TOY_EYES", "TEST_TOY_EYES_DONE", "TEST_TOY_END", "TEST_TOY_END_DONE", "NONE", "SETUP_STATUS",
    "ENABLE_USB_PORT", "END_LISTEN_FOR", "TOY_STATS", "GET_TOY_STATS", "UPDATE_PROFILE", "CLEAR_ACCOUNT",
    "NETWORK_WITHOUT_INTERNET", "GET_SETUP_STATE", "SETUP_STATE", "TEST_TOY_NOISE", "TEST_TOY_NOISE_DONE",
    "START_PLAY", "SET_ALARM", "ALARM_FIRED", "NETWORK_CONNECTION_FAILURE", "CURRENT_ACTIVITY",
    "CHECK_AND_UPDATE_TOY", "TOY_UPDATE_STATUS", "START_TOY_UPDATE", "SKIP_SETUP", "UPDATE_PROFILE_NAME",
    "UPDATE_PROFILE_JSON", "DISCONNECT_BLE", "TEST_TOY_DEVICE_INFO", "TEST_TOY_DEVICE_INFO_SENT",
    "PLAY_STARTED", "SPIDER_BUTTON_SHORT_PRESS", "SHUTDOWN_TOY", "TEST_TOY_EYES_TEST_MODE",
    "TEST_TOY_EYES_TEST_MODE_DONE", "TEST_TOY_EYES_TEST_MODE_VALUE", "ENABLE_AVS", "AVS_ENABLED",
    "DISABLE_AVS", "ENABLE_AVS_FAILED", "FORCE_TEAM_CHANGE", "PLAY_ONBOARDING_AUDIO", "SET_TIME_ZONE",
    "TEST_INTERNET_REACHABILITY", "REMOVE_ALL_WIFI_NETWORKS", "REMOVE_CURRENT_WIFI_NETWORK",
    "TOY_VOLUME_UPDATED", "TEST_TOY_AEC_MODE", "TEST_TOY_AEC_MODE_STARTED", "TEST_TOY_AEC_MODE_TEST_START",
    "TEST_TOY_AEC_MODE_TEST_END", "GET_PROFILE", "ATTACK", "PROFILE_JSON_VERSION", "PLAY_BEEP_SOUND",
    "UPDATE_SKIMMED_PROFILE", "NETWORK_PORT_BLOCKED", "CLEAR_NEW_PACKS_LIST", "SET_SENSOR_STATE",
]
Op = IntEnum("Op", {name: i for i, name in enumerate(_OPS)})

# Fire-and-forget command buttons exposed in HA (friendly-key -> op, sent with empty DT).
# HARDWARE-VERIFIED LIVE (2026-06-20) on the resurrected unit: after the LOGIN onboarding
# handshake (see coordinator), ATTACK produced a visible/audible interactive attack sequence,
# confirming action ops fire over BLE (the earlier "unprovisioned, not in dispatch" note was wrong).
# attack = confirmed; start_play / beep / sleep sent successfully in the same session.
SIMPLE_COMMANDS: dict[str, Op] = {
    "attack": Op.ATTACK,
    "beep": Op.PLAY_BEEP_SOUND,
    "start_play": Op.START_PLAY,
    "sleep": Op.SLEEP_TOY,
}

# Onboarding handshake the coordinator must run on connect before action ops are accepted.
# Verified: LOGIN with these creds (also what the cloud mock expects) + GET_SETUP_STATE clears
# the setup gate so ATTACK/etc. fire. Creds are the toy's bundled BLE login, not a secret to guard.
LOGIN_USER = "spidey"
LOGIN_PASS = "x"


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def gs(plaintext: str, key: bytes = XOR_KEY) -> str:
    """Encode a message string -> wire payload (XOR then base64)."""
    return base64.b64encode(_xor(plaintext.encode("utf-8"), key)).decode("ascii")


def gt(ciphertext: str, key: bytes = XOR_KEY) -> str:
    """Decode a wire payload -> message string (base64 then XOR)."""
    return _xor(base64.b64decode(ciphertext), key).decode("utf-8", errors="replace")


def build_message(op: Op | int, dt: str = "", sender_id: str | None = None,
                  acc: str | None = None, key: bytes = XOR_KEY) -> str:
    obj: dict = {K_OP: int(op), K_DT: dt}
    if sender_id is not None:
        obj[K_ID] = sender_id
    if acc is not None:
        obj[K_ACC] = acc
    return gs(json.dumps(obj, separators=(",", ":")), key)


def chunk_writes(encoded: str) -> list[bytes]:
    """Split an encoded payload into the BLE write sequence: #MS, <=20B chunks, #ME."""
    out = [MS]
    for i in range(0, len(encoded), CHUNK):
        out.append(encoded[i:i + CHUNK].encode("ascii"))
    out.append(ME)
    return out


def frame_command(op: Op | int, dt: str = "", **kw) -> list[bytes]:
    return chunk_writes(build_message(op, dt, **kw))


@dataclass
class ToyState:
    """Decoded, accumulated state of the figure (updated as frames arrive)."""
    battery_percent: int | None = None
    charging: bool | None = None
    firmware: str | None = None
    serial: str | None = None
    toy_name: str | None = None
    volume: int | None = None
    last_op: str | None = None
    last_button_press: float | None = None  # epoch seconds, set by coordinator
    raw: dict = field(default_factory=dict)


def parse_message(plain: str) -> dict:
    """Parse a decoded message string into a dict with the op name resolved."""
    out: dict = {"_plain": plain}
    try:
        j = json.loads(plain)
    except json.JSONDecodeError:
        return out
    out.update(j)
    op = j.get(K_OP)
    if op not in (None, ""):
        try:
            out["_op"] = Op(int(op))
            out["_op_name"] = Op(int(op)).name
        except (ValueError, KeyError):
            out["_op_name"] = f"?{op}"
    # DT is frequently itself a JSON object
    dt = j.get(K_DT)
    if isinstance(dt, str) and dt.startswith("{"):
        try:
            out["_dt"] = json.loads(dt)
        except json.JSONDecodeError:
            out["_dt"] = dt
    else:
        out["_dt"] = dt
    return out


def apply_to_state(state: ToyState, msg: dict) -> ToyState:
    """Fold a parsed message into ToyState.

    DT field codes verified against the toy firmware (com.smarttoy.l, com.smarttoy.embedded.b.c):
      PER = battery level, 0.0..1.0 float   CHG = charging flag (bool)
      VER = firmware version   SER = serial   TOY = toy id/name   VOL = volume, 0.0..1.0 float
      RES = test pass/fail (bool)            ACX/ACY/ACZ = accelerometer axes (float)
    """
    state.last_op = msg.get("_op_name")
    dt = msg.get("_dt")
    d = dt if isinstance(dt, dict) else {}

    if "PER" in d:  # appears in BATTERY_STATUS and INFO/INITIAL_DATA
        try:
            state.battery_percent = _as_percent(d["PER"])
        except (TypeError, ValueError):
            pass
    if "CHG" in d:
        state.charging = _as_bool(d["CHG"])
    if "VER" in d:
        state.firmware = str(d["VER"])
    if "SER" in d:
        state.serial = str(d["SER"])
    if "TOY" in d:
        state.toy_name = str(d["TOY"])
    if "VOL" in d:
        try:
            state.volume = _as_percent(d["VOL"])  # firmware sends 0.0..1.0
        except (TypeError, ValueError):
            pass

    state.raw = msg
    return state


def _as_bool(v) -> bool:
    return bool(v) and str(v).strip().lower() not in ("0", "false", "off", "")


def _as_percent(v) -> int:
    """Normalize a battery value that may be 0..1 or 0..100 into an int percent."""
    f = float(v)
    if 0.0 <= f <= 1.0:
        f *= 100.0
    return max(0, min(100, round(f)))


class Reassembler:
    """Reassemble inbound notify chunks (#MS .. #ME) and decode to a parsed dict."""

    def __init__(self, key: bytes = XOR_KEY) -> None:
        self.key = key
        self.buf = ""

    def feed(self, chunk: bytes) -> dict | None:
        """Feed one notify value; return a parsed message dict on completion, else None."""
        s = bytes(chunk).decode("ascii", errors="replace")
        if s == "#MS":
            self.buf = ""
            return None
        if s == "#ME":
            raw, self.buf = self.buf, ""
            try:
                return parse_message(gt(raw, self.key))
            except Exception:  # noqa: BLE001
                return {"_error": "decode-failed", "_raw": raw}
        self.buf += s
        return None
