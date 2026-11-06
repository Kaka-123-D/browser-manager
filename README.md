# Browser Manager

Local web app (http://127.0.0.1:17865) to open separate Chrome profiles on a Mac, each with its own cookies, timezone, language and optional VPN (WireGuard through wireproxy). It can also expose a VPN as a fixed local proxy with a login for other apps.

## Install on a new Mac
1. Install Google Chrome in Applications and Python 3.9 or newer.
2. Clone this repo, then double-click `start.command`. The first start makes a Python venv in `~/.browser-manager/venv`, installs Playwright, and downloads wireproxy (official release, SHA-256 checked) to `~/.local/bin`. macOS may ask you to allow `start.command` in System Settings → Privacy & Security the first time.
3. For VPN profiles, put WireGuard `.conf` files from your own VPN account in `~/.config/protonvpn/` (or `~/.config/surfshark/`). Each person needs their own configs: one WireGuard key used on two machines at once makes both connections drop.

## Data
Profiles, Chrome data, proxy logins and logs stay in `~/.browser-manager`, never in this repo.

## Tests
`~/.browser-manager/venv/bin/python -m unittest discover -s tests`
