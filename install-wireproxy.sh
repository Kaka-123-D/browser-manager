#!/bin/zsh
# Download the official wireproxy release for this Mac, check its SHA-256, install to ~/.local/bin.
# Usage: ./install-wireproxy.sh [target_dir]
set -euo pipefail
VERSION="v1.1.3"
BASE="https://github.com/windtf/wireproxy/releases/download/$VERSION"
TARGET_DIR="${1:-$HOME/.local/bin}"
case "$(uname -m)" in
  arm64) ARCH=arm64 ;;
  x86_64) ARCH=amd64 ;;
  *) echo "Máy này ($(uname -m)) chưa được hỗ trợ"; exit 1 ;;
esac
FILE="wireproxy_darwin_${ARCH}.tar.gz"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
echo "Đang tải wireproxy $VERSION ($ARCH)…"
curl -fsSL -o "$WORK/$FILE" "$BASE/$FILE"
curl -fsSL -o "$WORK/checksums.txt" "$BASE/checksums.txt"
EXPECTED="$(grep " $FILE\$" "$WORK/checksums.txt" | awk '{print $1}')"
ACTUAL="$(shasum -a 256 "$WORK/$FILE" | awk '{print $1}')"
if [[ -z "$EXPECTED" || "$EXPECTED" != "$ACTUAL" ]]; then
  echo "Mã kiểm tra không khớp, không cài"; exit 1
fi
tar -xzf "$WORK/$FILE" -C "$WORK" wireproxy
mkdir -p "$TARGET_DIR"
install -m 755 "$WORK/wireproxy" "$TARGET_DIR/wireproxy"
echo "Đã cài $("$TARGET_DIR/wireproxy" --version) vào $TARGET_DIR"
