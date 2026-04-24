#!/usr/bin/env sh
# KOPPA one-liner installer
# Usage:
#   curl -fsSL https://koppa.lang.co/install.sh | sh
#   wget -qO- https://koppa.lang.co/install.sh | sh

set -e

REPO="guea14012/koppa-lang"
VERSION="2.0.0"
INSTALL_DIR=""
BIN_NAME="koppa"

# ── Detect OS + arch ─────────────────────────────────────────────────────────
OS="$(uname -s 2>/dev/null || echo unknown)"
ARCH="$(uname -m 2>/dev/null || echo unknown)"

case "$OS" in
  Linux*)  PLATFORM="linux" ;;
  Darwin*) PLATFORM="macos" ;;
  MINGW*|MSYS*|CYGWIN*) PLATFORM="windows" ;;
  *)
    echo "[!] Unsupported OS: $OS"
    echo "    Download manually: https://github.com/$REPO/releases"
    exit 1
    ;;
esac

case "$ARCH" in
  x86_64|amd64) ARCH_TAG="x64" ;;
  arm64|aarch64) ARCH_TAG="arm64" ;;
  *)
    echo "[!] Unsupported architecture: $ARCH"
    exit 1
    ;;
esac

# ── Determine install directory ───────────────────────────────────────────────
if [ "$PLATFORM" = "windows" ]; then
  ASSET="koppa-windows-${ARCH_TAG}.exe"
  BIN_NAME="koppa.exe"
  INSTALL_DIR="$LOCALAPPDATA/koppa/bin"
  mkdir -p "$INSTALL_DIR"
else
  ASSET="koppa-${PLATFORM}-${ARCH_TAG}"
  # Prefer /usr/local/bin if writable, else ~/.local/bin
  if [ -w /usr/local/bin ]; then
    INSTALL_DIR="/usr/local/bin"
  else
    INSTALL_DIR="$HOME/.local/bin"
    mkdir -p "$INSTALL_DIR"
  fi
fi

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/v${VERSION}/${ASSET}"
DEST="${INSTALL_DIR}/${BIN_NAME}"

echo "Installing KOPPA v${VERSION} for ${PLATFORM}/${ARCH_TAG}..."
echo "  From: $DOWNLOAD_URL"
echo "  To  : $DEST"
echo ""

# ── Download ──────────────────────────────────────────────────────────────────
if command -v curl >/dev/null 2>&1; then
  curl -fsSL --progress-bar "$DOWNLOAD_URL" -o "$DEST"
elif command -v wget >/dev/null 2>&1; then
  wget -q --show-progress "$DOWNLOAD_URL" -O "$DEST"
else
  echo "[!] Neither curl nor wget found. Please install one and retry."
  exit 1
fi

chmod +x "$DEST"

# ── PATH hint ─────────────────────────────────────────────────────────────────
echo ""
echo "[+] Installed: $DEST"

if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
  echo ""
  echo "  Add to your PATH by appending to ~/.bashrc or ~/.zshrc:"
  echo "    export PATH=\"$INSTALL_DIR:\$PATH\""
fi

echo ""
echo "  Get started:"
echo "    koppa version"
echo "    koppa repl"
echo "    koppa run examples/hello.kop"
