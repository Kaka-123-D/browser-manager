"""Fixed proxies: one WireGuard config exposed on fixed local ports, with a username and password.

Other apps on this Mac can use them as http://user:pass@127.0.0.1:port or socks5://...
Records are immutable and stored in ~/.browser-manager/fixed_proxies.json (mode 600).
"""
from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from . import paths, proxy

FIRST_PORT = 18001
LAST_PORT = 18999


@dataclass(frozen=True)
class FixedProxy:
    key: str  # "vpn:<provider>/<file>.conf"
    http_port: int
    socks_port: int
    username: str
    password: str
    enabled: bool = False  # restart automatically when the manager starts

    def http_url(self) -> str:
        return f"http://{self.username}:{self.password}@127.0.0.1:{self.http_port}"

    def socks_url(self) -> str:
        return f"socks5://{self.username}:{self.password}@127.0.0.1:{self.socks_port}"

    def plain(self) -> str:
        """The ip:port:user:pass form many tools ask for."""
        return f"127.0.0.1:{self.http_port}:{self.username}:{self.password}"


def file_path() -> Path:
    return paths.DATA_DIR / "fixed_proxies.json"


def load() -> list[FixedProxy]:
    file = file_path()
    if not file.exists():
        return []
    try:
        rows = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{file} bị hỏng: {error}") from error
    return [FixedProxy(**row) for row in rows]


def save(records: list[FixedProxy]) -> None:
    file = file_path()
    tmp = file.with_suffix(".tmp")
    tmp.write_text(json.dumps([asdict(r) for r in records], indent=2), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(file)


def find(records: list[FixedProxy], key: str) -> FixedProxy | None:
    return next((r for r in records if r.key == key), None)


def new_record(key: str, records: list[FixedProxy]) -> FixedProxy:
    """Pick the next free pair of ports (http, socks) and a random login."""
    taken = {p for r in records for p in (r.http_port, r.socks_port)}
    for port in range(FIRST_PORT, LAST_PORT, 2):
        pair = (port, port + 1)
        if not any(p in taken or proxy.port_open(p) for p in pair):
            return FixedProxy(key, pair[0], pair[1], "bm" + secrets.token_hex(3), secrets.token_urlsafe(12))
    raise RuntimeError(f"Hết cổng trống trong khoảng {FIRST_PORT}-{LAST_PORT}")


def with_enabled(records: list[FixedProxy], key: str, enabled: bool) -> list[FixedProxy]:
    return [replace(r, enabled=enabled) if r.key == key else r for r in records]


def wireproxy_config(wg_conf: Path, record: FixedProxy) -> str:
    login = f"Username = {record.username}\nPassword = {record.password}\n"
    return (
        f"WGConfig = {wg_conf}\n\n"
        f"[http]\nBindAddress = 127.0.0.1:{record.http_port}\n{login}\n"
        f"[Socks5]\nBindAddress = 127.0.0.1:{record.socks_port}\n{login}"
    )
