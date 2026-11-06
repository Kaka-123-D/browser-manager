"""wireproxy processes: one local SOCKS5 port per WireGuard config, shared by profiles,
plus fixed proxies with a login (see fixed.py)."""
from __future__ import annotations

import json
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from . import paths

READY_TIMEOUT_S = 15


@dataclass(frozen=True)
class RunningProxy:
    key: str  # "vpn:<provider>/<file>.conf"
    port: int
    process: subprocess.Popen

    @property
    def url(self) -> str:
        return f"socks5://127.0.0.1:{self.port}"

    def alive(self) -> bool:
        return self.process.poll() is None


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# Proton configs carry an IPv6 address, so wireproxy would look up AAAA records first; some
# Google hosts (one.google.com) then hang forever while resolving. IPv4 first avoids that.
RESOLVE_SECTION = "[Resolve]\nResolveStrategy = ipv4\n"


def wireproxy_config(wg_conf: Path, port: int) -> str:
    return f"WGConfig = {wg_conf}\n\n{RESOLVE_SECTION}\n[Socks5]\nBindAddress = 127.0.0.1:{port}\n"


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def start(key: str, wg_conf: Path) -> RunningProxy:
    """Tunnel for profiles: SOCKS5 without login on a random loopback port."""
    port = free_port()
    slug = key.replace("vpn:", "").replace("/", "_")
    return launch(key, slug, wireproxy_config(wg_conf, port), port)


def launch(key: str, slug: str, config_text: str, ready_port: int) -> RunningProxy:
    """Run wireproxy with the given config and wait until ready_port accepts connections."""
    if not paths.WIREPROXY_BIN.exists():
        raise RuntimeError(f"Chưa có wireproxy ở {paths.WIREPROXY_BIN}. Thoát Browser Manager rồi mở lại bằng start.command để tự cài, hoặc chạy ./install-wireproxy.sh")
    conf_file = paths.PROXY_CONF_DIR / f"{slug}.conf"
    conf_file.write_text(config_text, encoding="utf-8")
    conf_file.chmod(0o600)
    log = open(paths.LOG_DIR / f"proxy-{slug}.log", "ab")
    process = subprocess.Popen([str(paths.WIREPROXY_BIN), "-c", str(conf_file)], stdout=log, stderr=log)
    log.close()
    deadline = time.monotonic() + READY_TIMEOUT_S
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"wireproxy thoát sớm, xem {paths.LOG_DIR}/proxy-{slug}.log")
        if port_open(ready_port):
            return RunningProxy(key, ready_port, process)
        time.sleep(0.3)
    process.terminate()
    raise RuntimeError(f"wireproxy không mở cổng {ready_port} sau {READY_TIMEOUT_S}s")


def stop(proxy: RunningProxy) -> None:
    if proxy.alive():
        proxy.process.terminate()
        try:
            proxy.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proxy.process.kill()


def lookup_exit(proxy_url: str) -> dict:
    """Ask ipinfo.io which IP/country/timezone the given proxy exits from ('' = direct)."""
    cmd = ["curl", "-s", "--max-time", "20", "https://ipinfo.io/json"]
    if proxy_url.startswith("socks5://"):
        cmd[1:1] = ["--socks5-hostname", proxy_url.removeprefix("socks5://")]
    elif proxy_url:
        cmd[1:1] = ["--proxy", proxy_url]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("Không kiểm tra được IP qua proxy (proxy chết hoặc mất mạng)") from error
    return {k: data.get(k, "") for k in ("ip", "country", "region", "city", "org", "timezone")}
