"""Local web UI + JSON API on 127.0.0.1 only.

Every write request must carry the header X-BM: 1 and a 127.0.0.1/localhost Host,
so a web page open in another tab cannot drive the manager.
"""
from __future__ import annotations

import json
import re
import signal
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import paths, store
from .manager import Manager

INDEX_HTML = Path(__file__).with_name("static") / "index.html"
ACTION_RE = re.compile(r"^/api/profiles/([a-z0-9-]+)/(start|stop|ip)$")
PROFILE_RE = re.compile(r"^/api/profiles/([a-z0-9-]+)$")
ALLOWED_HOSTS = {f"127.0.0.1:{paths.SERVER_PORT}", f"localhost:{paths.SERVER_PORT}"}
MAX_BODY = 16_384

manager: Manager | None = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # keep the terminal quiet
        return

    def do_GET(self) -> None:
        if not self._host_ok():
            return self._send(403, {"error": "forbidden"})
        if self.path == "/":
            return self._send_html()
        if self.path == "/api/state":
            return self._send(200, manager.state())
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        self._write_request(self._route_post)

    def do_DELETE(self) -> None:
        self._write_request(self._route_delete)

    # ---- routing ----
    def _route_post(self) -> dict:
        if self.path == "/api/profiles":
            manager.save_profile(self._json_body())
            return {"ok": True}
        match = ACTION_RE.match(self.path)
        if not match:
            raise LookupError
        name, action = match.groups()
        if action == "start":
            manager.start(name)
        elif action == "stop":
            manager.stop(name)
        else:
            return {"ok": True, "exit": manager.check_ip(name)}
        return {"ok": True}

    def _route_delete(self) -> dict:
        match = PROFILE_RE.match(self.path)
        if not match:
            raise LookupError
        manager.delete_profile(match.group(1))
        return {"ok": True}

    def _write_request(self, route) -> None:
        if not self._host_ok() or self.headers.get("X-BM") != "1":
            return self._send(403, {"error": "forbidden"})
        try:
            self._send(200, route())
        except LookupError:
            self._send(404, {"error": "not found"})
        except store.ValidationError as error:
            self._send(400, {"error": str(error)})
        except RuntimeError as error:
            self._send(500, {"error": str(error)})

    # ---- helpers ----
    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in ALLOWED_HOSTS

    def _json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise store.ValidationError("Dữ liệu gửi lên quá lớn")
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as error:
            raise store.ValidationError("JSON không hợp lệ") from error
        if not isinstance(body, dict):
            raise store.ValidationError("JSON phải là object")
        return body

    def _send(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self) -> None:
        data = INDEX_HTML.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    global manager
    manager = Manager()
    server = ThreadingHTTPServer((paths.SERVER_HOST, paths.SERVER_PORT), Handler)

    def shutdown(*_):
        manager.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    print(f"Browser Manager: http://127.0.0.1:{paths.SERVER_PORT}  (Ctrl+C để tắt)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
