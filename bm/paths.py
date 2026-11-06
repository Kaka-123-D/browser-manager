"""Fixed locations used by the manager."""
import shutil
from pathlib import Path

HOME = Path.home()
DATA_DIR = HOME / ".browser-manager"
PROFILES_FILE = DATA_DIR / "profiles.json"
PROFILE_DATA_DIR = DATA_DIR / "profiles"
PROXY_CONF_DIR = DATA_DIR / "proxies"
LOG_DIR = DATA_DIR / "logs"
VENV_PYTHON = DATA_DIR / "venv" / "bin" / "python"
_LOCAL_WIREPROXY = HOME / ".local" / "bin" / "wireproxy"
# Prefer ~/.local/bin (install-wireproxy.sh puts it there), else any wireproxy on PATH.
WIREPROXY_BIN = Path(shutil.which("wireproxy") or _LOCAL_WIREPROXY) if not _LOCAL_WIREPROXY.exists() else _LOCAL_WIREPROXY
CHROME_BIN = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

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
