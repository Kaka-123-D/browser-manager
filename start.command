#!/bin/zsh
# Double-click in Finder (or run in Terminal) to start Browser Manager.
cd "$(dirname "$0")"
PORT=17865
URL="http://127.0.0.1:$PORT"
PY="$HOME/.browser-manager/venv/bin/python"
if [[ ! -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]]; then
  echo "Cần cài Google Chrome vào thư mục Applications trước: https://www.google.com/chrome/"
  exit 1
fi
if [[ ! -x "$PY" ]]; then
  SYS_PY="$(command -v python3 || true)"
  if [[ -z "$SYS_PY" ]] || ! "$SYS_PY" -c 'import sys; sys.exit(sys.version_info < (3, 9))'; then
    echo "Cần Python 3.9 trở lên: https://www.python.org/downloads/macos/"
    exit 1
  fi
  "$SYS_PY" -m venv "$HOME/.browser-manager/venv" && "$PY" -m pip install -q playwright || exit 1
fi
if [[ ! -x "$HOME/.local/bin/wireproxy" ]] && ! command -v wireproxy >/dev/null; then
  ./install-wireproxy.sh || exit 1
fi
# Already running? Only trust a reply that really is Browser Manager's API.
if curl -s --max-time 2 "$URL/api/state" | grep -q '"vpn_configs"'; then
  open "$URL"
  exit 0
fi
if lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Cổng $PORT đang bị chương trình khác dùng. Sửa SERVER_PORT trong bm/paths.py và PORT ở file này."
  exit 1
fi
(sleep 1 && open "$URL") &
exec "$PY" -m bm.server
