"""Constants for the Sphero Spider-Man integration."""
from __future__ import annotations

DOMAIN = "sphero_spiderman"

# BLE local-name prefix the figure advertises (e.g. "ST8eab6d"). It does NOT advertise
# the service UUID, so discovery must match on the name prefix.
NAME_PREFIX = "ST"

# Connection / reconnect tuning
RECONNECT_BACKOFF_MIN = 3.0
RECONNECT_BACKOFF_MAX = 60.0
STALE_AFTER = 90.0  # seconds without a frame before we tear down + reconnect

# Eye-expression control (root/SSH bonus surface — see eyes.py). Optional; the Select entity
# is only created when BOTH an SSH key and host are configured.
CONF_EYE_HOST = "eye_ssh_host"
CONF_EYE_PORT = "eye_ssh_port"
CONF_EYE_USER = "eye_ssh_user"
CONF_EYE_KEY = "eye_ssh_key"  # path to a private key readable by Home Assistant

DEFAULT_EYE_HOST = ""  # set to your figure's IP/host; defaults to the dropbear port + root user
DEFAULT_EYE_PORT = 2222
DEFAULT_EYE_USER = "root"
