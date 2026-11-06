"""Child process: open one Chrome profile with Playwright and wait until it is closed.

Usage: python -m bm.runner '<json settings>'
"""
from __future__ import annotations

import json
import sys

from playwright.sync_api import sync_playwright

# Keep WebRTC from leaking the real IP around the proxy.
WEBRTC_ARGS = [
    "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    "--webrtc-ip-handling-policy=disable_non_proxied_udp",
]


def launch_options(settings: dict) -> dict:
    options = {
        "user_data_dir": settings["data_dir"],
        "channel": "chrome",
        "headless": False,
        "no_viewport": True,
        "locale": settings["locale"],
        "args": WEBRTC_ARGS,
    }
    if settings.get("cdp_port"):
        # Loopback-only DevTools port so local scripts can attach with connect_over_cdp.
        options["args"] = [*WEBRTC_ARGS, f"--remote-debugging-port={settings['cdp_port']}"]
    if settings.get("timezone"):
        options["timezone_id"] = settings["timezone"]
    if settings.get("proxy_url"):
        options["proxy"] = {"server": settings["proxy_url"]}
    return options


def main() -> int:
    settings = json.loads(sys.argv[1])
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(**launch_options(settings))
        page = context.pages[0] if context.pages else context.new_page()
        if settings.get("start_url", "about:blank") != "about:blank":
            page.goto(settings["start_url"])
        context.wait_for_event("close", timeout=0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
