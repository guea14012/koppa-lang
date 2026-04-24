#!/usr/bin/env sh
# KOPPA one-liner installer
# Usage:
#   curl -fsSL https://guea14012.github.io/koppa-lang/install.sh | sh

set -e

REPO="guea14012/koppa-lang"
VERSION="2.0.0"
BIN_NAME="koppa"

OS="$(uname -s 2>/dev/null || echo unknown)"
ARCH="$(uname -m 2>/dev/null || echo unknown)"

case "$OS" in
  Linux*)  PLATFORM="linux" ;;
  Darwin*) PLATFORM="macos" ;;
  MINGW*|MSYS*|CYGWIN*) PLATFORM="windows" ;;
  *)
    echo "[!] Unsupported OS: $OS"
    echo "    Try: pip install koppa-lang"
    exit 1
    ;;
esac

echo "Installing KOPPA v${VERSION}..."

# Fallback to pip (always works)
if command -v pip3 >/dev/null 2>&1; then
  pip3 install koppa-lang
elif command -v pip >/dev/null 2>&1; then
  pip install koppa-lang
else
  echo "[!] pip not found. Install Python 3.8+ first: https://python.org"
  exit 1
fi

echo ""
echo "[+] KOPPA installed successfully!"
echo ""
echo "  Get started:"
echo "    koppa version"
echo "    koppa repl"
