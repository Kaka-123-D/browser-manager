"""Fixed locations used by the manager."""
from pathlib import Path

HOME = Path.home()
DATA_DIR = HOME / ".browser-manager"
PROFILES_FILE = DATA_DIR / "profiles.json"
PROFILE_DATA_DIR = DATA_DIR / "profiles"
PROXY_CONF_DIR = DATA_DIR / "proxies"
LOG_DIR = DATA_DIR / "logs"
VENV_PYTHON = DATA_DIR / "venv" / "bin" / "python"
WIREPROXY_BIN = HOME / ".local" / "bin" / "wireproxy"

# WireGuard configs downloaded from VPN providers, one sub-folder per provider.
VPN_DIRS = {
    "protonvpn": HOME / ".config" / "protonvpn",
    "surfshark": HOME / ".config" / "surfshark",
}

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 17865


def ensure_dirs() -> None:
    for directory in (DATA_DIR, PROFILE_DATA_DIR, PROXY_CONF_DIR, LOG_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    PROXY_CONF_DIR.chmod(0o700)
