"""Golden-frame + round-trip tests for the pure protocol module (no HA deps)."""
import importlib.util
import json
import sys
from pathlib import Path

# Load custom_components/sphero_spiderman/protocol.py directly (no HA install needed).
_PROTO = Path(__file__).resolve().parents[1] / "custom_components" / "sphero_spiderman" / "protocol.py"
_spec = importlib.util.spec_from_file_location("sphero_protocol", _PROTO)
P = importlib.util.module_from_spec(_spec)
sys.modules["sphero_protocol"] = P  # needed so @dataclass can introspect the module
_spec.loader.exec_module(P)


def test_key_is_15_chars():
    assert P.XOR_KEY == b"$u?4dMk?ii/;b0g"
    assert len(P.XOR_KEY) == 15


def test_op_ordinals():
    # Ordinals are load-bearing (they go on the wire). Pin the important ones.
    assert int(P.Op.PLAY_ACTIVITY) == 2
    assert int(P.Op.GET_BATTERY_STATUS) == 11
    assert int(P.Op.INFO) == 16
    assert int(P.Op.BATTERY_STATUS) == 23
    assert int(P.Op.ATTACK) == 106
    assert int(P.Op.PLAY_BEEP_SOUND) == 108


def test_gs_gt_round_trip():
    for s in ('{"OP":11,"DT":""}', '{"OP":23,"DT":"{\\"CHG\\":true,\\"PER\\":0.85}"}', "héllo"):
        assert P.gt(P.gs(s)) == s


def test_build_get_battery_status_golden():
    enc = P.build_message(P.Op.GET_BATTERY_STATUS, "")
    # Golden value derived from the recovered key; locks the encoder.
    assert enc == "X1dwZEZ3Wg5FS2tvQApFBgg="
    assert P.gt(enc) == '{"OP":11,"DT":""}'


def test_chunk_writes_framing():
    writes = P.frame_command(P.Op.GET_BATTERY_STATUS, "")
    assert writes[0] == b"#MS"
    assert writes[-1] == b"#ME"
    # middle chunks are <= 20 bytes and rejoin to the encoded payload
    body = b"".join(writes[1:-1]).decode()
    assert body == P.build_message(P.Op.GET_BATTERY_STATUS, "")
    assert all(len(w) <= P.CHUNK for w in writes[1:-1])


def _frames_for(op, dt_obj):
    msg = json.dumps({"OP": int(op), "DT": json.dumps(dt_obj, separators=(",", ":"))},
                     separators=(",", ":"))
    return P.chunk_writes(P.gs(msg))


def test_reassembler_decodes_battery_status():
    re = P.Reassembler()
    out = None
    for w in _frames_for(P.Op.BATTERY_STATUS, {"CHG": True, "PER": 0.85}):
        out = re.feed(w) or out
    assert out is not None
    assert out["_op_name"] == "BATTERY_STATUS"
    state = P.apply_to_state(P.ToyState(), out)
    assert state.battery_percent == 85
    assert state.charging is True


def test_apply_info_fields():
    re = P.Reassembler()
    out = None
    for w in _frames_for(P.Op.INFO, {"TOY": "ST8eab6d", "SER": "SM123", "VER": "1.2.3", "VOL": 0.8}):
        out = re.feed(w) or out
    state = P.apply_to_state(P.ToyState(), out)
    assert state.firmware == "1.2.3"
    assert state.serial == "SM123"
    assert state.toy_name == "ST8eab6d"
    assert state.volume == 80


def test_percent_normalization():
    assert P._as_percent(0.85) == 85
    assert P._as_percent(1.0) == 100
    assert P._as_percent(50) == 50
    assert P._as_percent(0) == 0


def test_characteristic_roles():
    # Verified against the toy's GATT server (com.smarttoy.ble.a.b):
    # commands -> 81E4C615, status notify <- 740563D5, per-chunk ack -> 1EAEBABD.
    assert P.CHAR_WRITE == "81e4c615-62f2-48b6-8be4-96dcd0801bb7"
    assert P.CHAR_NOTIFY == "740563d5-3736-4033-87b5-029c38ccc893"
    assert P.CHAR_ACK == "1eaebabd-4ce8-48c3-a1fc-fbe733e1e6ea"


# ---- GOLDEN FRAMES captured live from unit ST8eab6d (real on-wire bytes) -------------
# These are the reassembled #MS..#ME payloads (key validation against real hardware).
REAL_BATTERY = "X1dwZEZ3WQxFS2Z/QApFQEwHUQUvXVtLRQ1/NhJdBg5jFicFLGNLU1tJF1VLeFdvcTYRSQVYFA1G"
REAL_SETUP = "X1dwZEZ3XQhFS2Z/QApFQEwHUQUvXVtLRQ1/NhJdBg5jFjceOGNLU0laDkMCCCkdZzcfNx1TMh1mHxIa"


def test_golden_live_battery_status():
    msg = P.parse_message(P.gt(REAL_BATTERY))
    assert msg["_op_name"] == "BATTERY_STATUS"
    assert msg["ID"] == "d98eab6d"
    state = P.apply_to_state(P.ToyState(), msg)
    assert state.battery_percent == 100
    assert state.charging is True


def test_golden_live_setup_state():
    msg = P.parse_message(P.gt(REAL_SETUP))
    assert msg["_op_name"] == "SETUP_STATE"
    assert msg["_dt"] == {"SSS": False, "SSR": [2]}  # not provisioned
