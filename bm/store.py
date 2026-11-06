"""Profile records: validation and JSON storage (records are immutable)."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from zoneinfo import available_timezones

from . import paths

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
VPN_RE = re.compile(r"^vpn:([a-z]+)/([A-Za-z0-9._-]+\.conf)$")
URL_PROXY_RE = re.compile(r"^(http|socks5)://[A-Za-z0-9.-]+:\d{2,5}$")
LOCALE_RE = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


class ValidationError(ValueError):
    """Raised when user input for a profile is not acceptable."""


@dataclass(frozen=True)
class Profile:
    name: str
    proxy: str = ""  # "", "vpn:<provider>/<file>.conf" or "<scheme>://host:port"
    timezone: str = "auto"
    locale: str = "en-US"
    start_url: str = "about:blank"
    note: str = ""

    @property
    def data_dir(self) -> Path:
        return paths.PROFILE_DATA_DIR / self.name


def list_vpn_configs(vpn_dirs: dict[str, Path] | None = None) -> list[str]:
    """Return proxy values like 'vpn:protonvpn/us-wa-270.conf' for every config on disk."""
    found = []
    for provider, directory in sorted((vpn_dirs or paths.VPN_DIRS).items()):
        if directory.is_dir():
            found.extend(f"vpn:{provider}/{p.name}" for p in sorted(directory.glob("*.conf")))
    return found


def vpn_config_path(proxy: str, vpn_dirs: dict[str, Path] | None = None) -> Path | None:
    match = VPN_RE.match(proxy)
    if not match:
        return None
    directory = (vpn_dirs or paths.VPN_DIRS).get(match.group(1))
    return directory / match.group(2) if directory else None


def validate(raw: dict, vpn_dirs: dict[str, Path] | None = None) -> Profile:
    name = str(raw.get("name", "")).strip()
    if not NAME_RE.match(name):
        raise ValidationError("Tên chỉ gồm a-z, 0-9, dấu '-' (tối đa 40 ký tự)")
    proxy = str(raw.get("proxy", "")).strip()
    _validate_proxy(proxy, vpn_dirs)
    timezone = str(raw.get("timezone", "auto")).strip() or "auto"
    if timezone != "auto" and timezone not in available_timezones():
        raise ValidationError(f"Múi giờ không hợp lệ: {timezone}")
    locale = str(raw.get("locale", "en-US")).strip() or "en-US"
    if not LOCALE_RE.match(locale):
        raise ValidationError(f"Locale không hợp lệ: {locale}")
    start_url = str(raw.get("start_url", "")).strip() or "about:blank"
    if not (start_url == "about:blank" or start_url.startswith(("http://", "https://"))):
        raise ValidationError("Trang mở đầu phải bắt đầu bằng http:// hoặc https://")
    note = str(raw.get("note", "")).strip()[:200]
    return Profile(name, proxy, timezone, locale, start_url, note)


def _validate_proxy(proxy: str, vpn_dirs: dict[str, Path] | None) -> None:
    if proxy == "" or URL_PROXY_RE.match(proxy):
        return
    conf = vpn_config_path(proxy, vpn_dirs)
    if conf is None:
        raise ValidationError("Proxy phải trống, vpn:<nhà>/<file>.conf hoặc http(s)/socks5://host:port")
    if not conf.is_file():
        raise ValidationError(f"Không thấy file cấu hình {conf}")


def load(path: Path | None = None) -> list[Profile]:
    file = path or paths.PROFILES_FILE
    if not file.exists():
        return []
    try:
        rows = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{file} bị hỏng: {error}") from error
    return [Profile(**row) for row in rows]


def save(profiles: list[Profile], path: Path | None = None) -> None:
    file = path or paths.PROFILES_FILE
    tmp = file.with_suffix(".tmp")
    tmp.write_text(json.dumps([asdict(p) for p in profiles], indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(file)


def upsert(profiles: list[Profile], profile: Profile) -> list[Profile]:
    others = [p for p in profiles if p.name != profile.name]
    return sorted([*others, profile], key=lambda p: p.name)


def remove(profiles: list[Profile], name: str) -> list[Profile]:
    return [p for p in profiles if p.name != name]


def find(profiles: list[Profile], name: str) -> Profile | None:
    return next((p for p in profiles if p.name == name), None)
