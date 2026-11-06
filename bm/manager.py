"""Ties profiles, wireproxy processes and Chrome windows together (thread-safe)."""
from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

from . import fixed, paths, proxy, store

APP_ROOT = Path(__file__).resolve().parent.parent


class Manager:
    def __init__(self) -> None:
        paths.ensure_dirs()
        self._lock = threading.Lock()
        self._profiles = store.load()
        self._proxies: dict[str, proxy.RunningProxy] = {}
        self._browsers: dict[str, subprocess.Popen] = {}
        self._cdp_ports: dict[str, int] = {}
        self._fixed = fixed.load()
        self._fixed_running: dict[str, proxy.RunningProxy] = {}
        threading.Thread(target=self._autostart_fixed, daemon=True).start()

    # ---- read ----
    def state(self) -> dict:
        with self._lock:
            self._reap()
            return {
                "profiles": [
                    {**p.__dict__, "running": p.name in self._browsers, "cdp_port": self._cdp_ports.get(p.name)}
                    for p in self._profiles
                ],
                "vpn_configs": store.list_vpn_configs(),
                "proxies": [{"key": k, "port": p.port} for k, p in self._proxies.items()],
                "fixed": [self._fixed_view(r) for r in self._fixed],
            }

    def _fixed_view(self, record: fixed.FixedProxy) -> dict:
        return {
            "key": record.key, "http_port": record.http_port, "socks_port": record.socks_port,
            "username": record.username, "password": record.password, "enabled": record.enabled,
            "http_url": record.http_url(), "socks_url": record.socks_url(), "plain": record.plain(),
            "running": record.key in self._fixed_running,
        }

    # ---- profiles ----
    def save_profile(self, raw: dict) -> None:
        profile = store.validate(raw)
        old_name = str(raw.get("rename_from") or profile.name)
        with self._lock:
            if profile.name in self._browsers or old_name in self._browsers:
                raise store.ValidationError("Đóng Chrome của profile này trước khi sửa")
            if old_name != profile.name:
                self._rename_data(old_name, profile.name)
            self._profiles = store.upsert(store.remove(self._profiles, old_name), profile)
            store.save(self._profiles)

    def _rename_data(self, old_name: str, new_name: str) -> None:
        """Move the Chrome data folder so logins/cookies follow the new name."""
        self._require(old_name)
        if store.find(self._profiles, new_name):
            raise store.ValidationError(f"Đã có profile tên {new_name}")
        old_dir, new_dir = paths.PROFILE_DATA_DIR / old_name, paths.PROFILE_DATA_DIR / new_name
        if new_dir.exists():
            raise store.ValidationError(f"Thư mục {new_dir} đã tồn tại, chọn tên khác")
        if old_dir.exists():
            old_dir.rename(new_dir)

    def delete_profile(self, name: str) -> None:
        with self._lock:
            if name in self._browsers:
                raise store.ValidationError("Đóng Chrome của profile này trước khi xoá")
            self._profiles = store.remove(self._profiles, name)
            store.save(self._profiles)

    # ---- browsers ----
    def start(self, name: str) -> None:
        with self._lock:
            self._reap()
            profile = self._require(name)
            if name in self._browsers:
                raise store.ValidationError("Profile này đang mở")
            proxy_url = self._proxy_url(profile)
        timezone = self._timezone(profile, proxy_url)
        settings = {
            "data_dir": str(profile.data_dir),
            "proxy_url": proxy_url,
            "timezone": timezone,
            "locale": profile.locale,
            "start_url": profile.start_url,
            "cdp_port": proxy.free_port(),
        }
        log = open(paths.LOG_DIR / f"browser-{name}.log", "ab")
        process = subprocess.Popen(
            [str(paths.VENV_PYTHON), "-m", "bm.runner", json.dumps(settings)],
            cwd=APP_ROOT, stdout=log, stderr=log,
        )
        log.close()
        with self._lock:
            self._browsers = {**self._browsers, name: process}
            self._cdp_ports = {**self._cdp_ports, name: settings["cdp_port"]}

    def stop(self, name: str) -> None:
        with self._lock:
            process = self._browsers.get(name)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        with self._lock:
            self._reap()

    def check_ip(self, name: str) -> dict:
        with self._lock:
            proxy_url = self._proxy_url(self._require(name))
        return proxy.lookup_exit(proxy_url)

    def shutdown(self) -> None:
        for name in list(self._browsers):
            self.stop(name)
        with self._lock:
            for running in [*self._proxies.values(), *self._fixed_running.values()]:
                proxy.stop(running)
            self._proxies = {}
            self._fixed_running = {}

    # ---- fixed proxies ----
    def add_fixed(self, key: str) -> None:
        with self._lock:
            if key not in store.list_vpn_configs():
                raise store.ValidationError(f"Không có máy chủ VPN {key}")
            if fixed.find(self._fixed, key):
                raise store.ValidationError("Máy chủ này đã có proxy cố định")
            self._fixed = [*self._fixed, fixed.new_record(key, self._fixed)]
            fixed.save(self._fixed)

    def start_fixed(self, key: str) -> None:
        with self._lock:
            self._reap()
            record = self._require_fixed(key)
            if key in self._fixed_running:
                return
            if key in self._proxies:
                raise store.ValidationError("Đang có Chrome dùng máy chủ này qua đường hầm riêng. Đóng nó rồi bật lại.")
            conf = store.vpn_config_path(key)
            if conf is None or not conf.is_file():
                raise store.ValidationError(f"Không thấy file cấu hình cho {key}")
            slug = "fixed_" + key.replace("vpn:", "").replace("/", "_")
            running = proxy.launch(key, slug, fixed.wireproxy_config(conf, record), record.http_port)
            self._fixed_running = {**self._fixed_running, key: running}
            self._fixed = fixed.with_enabled(self._fixed, key, True)
            fixed.save(self._fixed)

    def stop_fixed(self, key: str) -> None:
        with self._lock:
            self._reap()
            self._require_fixed(key)
            users = [n for n in self._browsers if (p := store.find(self._profiles, n)) and p.proxy == key]
            if users:
                raise store.ValidationError(f"Chrome {', '.join(users)} đang đi qua proxy này, đóng trước")
            running = self._fixed_running.get(key)
            if running:
                proxy.stop(running)
            self._fixed_running = {k: v for k, v in self._fixed_running.items() if k != key}
            self._fixed = fixed.with_enabled(self._fixed, key, False)
            fixed.save(self._fixed)

    def delete_fixed(self, key: str) -> None:
        with self._lock:
            self._require_fixed(key)
            if key in self._fixed_running:
                raise store.ValidationError("Tắt proxy này trước khi xoá")
            self._fixed = [r for r in self._fixed if r.key != key]
            fixed.save(self._fixed)

    def check_fixed_ip(self, key: str) -> dict:
        with self._lock:
            record = self._require_fixed(key)
            if key not in self._fixed_running:
                raise store.ValidationError("Bật proxy trước khi kiểm IP")
        return proxy.lookup_exit(record.http_url())

    def _autostart_fixed(self) -> None:
        for record in [r for r in self._fixed if r.enabled]:
            try:
                self.start_fixed(record.key)
            except (store.ValidationError, RuntimeError) as error:
                print(f"Không bật lại được proxy cố định {record.key}: {error}")

    # ---- internals (call with lock held) ----
    def _require(self, name: str) -> store.Profile:
        profile = store.find(self._profiles, name)
        if profile is None:
            raise store.ValidationError(f"Không có profile {name}")
        return profile

    def _require_fixed(self, key: str) -> fixed.FixedProxy:
        record = fixed.find(self._fixed, key)
        if record is None:
            raise store.ValidationError(f"Không có proxy cố định cho {key}")
        return record

    def _proxy_url(self, profile: store.Profile) -> str:
        if not profile.proxy.startswith("vpn:"):
            return profile.proxy
        if profile.proxy in self._fixed_running:
            # One tunnel per WireGuard key: reuse the fixed proxy instead of opening a second one.
            return self._require_fixed(profile.proxy).http_url()
        running = self._proxies.get(profile.proxy)
        if running is None or not running.alive():
            conf = store.vpn_config_path(profile.proxy)
            if conf is None or not conf.is_file():
                raise store.ValidationError(f"Không thấy file cấu hình cho {profile.proxy}")
            running = proxy.start(profile.proxy, conf)
            self._proxies = {**self._proxies, profile.proxy: running}
        return running.url

    @staticmethod
    def _timezone(profile: store.Profile, proxy_url: str) -> str:
        if profile.timezone != "auto":
            return profile.timezone
        if not proxy_url:
            return ""  # follow the Mac's own timezone
        return proxy.lookup_exit(proxy_url).get("timezone", "")

    def _reap(self) -> None:
        """Forget closed windows; stop VPN tunnels no open window uses any more."""
        self._browsers = {n: p for n, p in self._browsers.items() if p.poll() is None}
        self._cdp_ports = {n: port for n, port in self._cdp_ports.items() if n in self._browsers}
        in_use = {store.find(self._profiles, n).proxy for n in self._browsers if store.find(self._profiles, n)}
        idle = {k: p for k, p in self._proxies.items() if k not in in_use or not p.alive()}
        for running in idle.values():
            proxy.stop(running)
        self._proxies = {k: p for k, p in self._proxies.items() if k not in idle}
        self._fixed_running = {k: p for k, p in self._fixed_running.items() if p.alive()}
