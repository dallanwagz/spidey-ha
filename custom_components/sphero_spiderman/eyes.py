"""Eye-expression control — the toy's root/SSH bonus surface (NOT the BLE path).

The eyes are a Tenx animation MCU on I2C, exposed at /sys/class/dsp/. Unlike the rest of
this integration (BLE), expressions are selected by writing the ASCII string
  <L_opcode><brightness><R_opcode><brightness>
to /sys/class/dsp/dsp_reg as root. Opcodes reverse-engineered from the toy firmware
(com/smarttoy/embedded/controllers/a.java) and verified live. Because this needs a root
shell on the toy (our resurrection installed dropbear on :2222), it's a separate transport
from the BLE coordinator and is intentionally kept out of the core/PR-able BLE path.

Requires `asyncssh`. SSH target + key come from the config entry options (see const).
"""
from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

BRIGHT = "ff"

# expression -> (left_opcode, right_opcode) hex. * = verified on hardware 2026-06-20.
EYE_EXPRESSIONS: dict[str, tuple[str, str]] = {
    "neutral": ("19", "8A"),    # *
    "happy": ("13", "84"),      # *
    "mad": ("1F", "90"),        # *
    "blink": ("10", "81"),      # *
    "laugh": ("12", "83"),
    "surprised": ("15", "86"),
    "squinting": ("16", "87"),
    "look_around": ("1A", "8B"),
    "sleepy": ("1D", "8E"),
    "wink": ("11", "82"),
}


def dsp_code(name: str) -> str:
    """Return the 8-char dsp_reg string for an expression name."""
    left, right = EYE_EXPRESSIONS[name]
    return f"{left}{BRIGHT}{right}{BRIGHT}".lower()


def _remote_command(name: str) -> str:
    """Shell command run on the toy to power the eye DSP and select the expression."""
    code = dsp_code(name)
    return (
        "echo 1 > /sys/class/dsp/dsp_pwr 2>/dev/null; "
        "echo 1 > /sys/class/dsp/en_state 2>/dev/null; "
        f"echo -n {code} > /sys/class/dsp/dsp_reg"
    )


async def async_set_expression(
    name: str, *, host: str, port: int, username: str, client_keys: list[str]
) -> None:
    """Set an eye expression over SSH (root on the toy). Raises on connection failure."""
    import asyncssh  # imported lazily so the BLE path has no hard asyncssh dependency

    if name not in EYE_EXPRESSIONS:
        raise ValueError(f"unknown expression {name!r}")
    async with asyncssh.connect(
        host, port=port, username=username, client_keys=client_keys, known_hosts=None
    ) as conn:
        result = await conn.run(_remote_command(name), check=False)
        if result.exit_status:
            _LOGGER.warning("eye set %s exited %s: %s", name, result.exit_status, result.stderr)
