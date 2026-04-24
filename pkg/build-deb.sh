#!/usr/bin/env bash
# Build a .deb package for KOPPA
# Requires: dpkg-deb (sudo apt install dpkg)
#
# Usage:
#   bash pkg/build-deb.sh                    # builds koppa_2.0.0_amd64.deb
#   bash pkg/build-deb.sh --version 2.1.0
#
# The resulting .deb can be installed with:
#   sudo dpkg -i koppa_2.0.0_amd64.deb
# Or added to an apt repo for one-line install.

set -e

VERSION="${1:-2.0.0}"
ARCH="amd64"
PKG_NAME="koppa_${VERSION}_${ARCH}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="/tmp/${PKG_NAME}"

echo "Building .deb for KOPPA v${VERSION}..."

# ── Create debian directory structure ────────────────────────────────────────
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/local/bin"
mkdir -p "$BUILD_DIR/usr/local/lib/koppa/stdlib"
mkdir -p "$BUILD_DIR/usr/local/lib/koppa/examples"
mkdir -p "$BUILD_DIR/usr/share/doc/koppa"

# ── control file ─────────────────────────────────────────────────────────────
cat > "$BUILD_DIR/DEBIAN/control" <<EOF
Package: koppa
Version: ${VERSION}
Section: devel
Priority: optional
Architecture: ${ARCH}
Depends: python3 (>= 3.8)
Maintainer: YOUR_NAME <your@email.com>
Homepage: https://github.com/YOUR_USERNAME/koppa-lang
Description: Advanced Pentesting Domain-Specific Language
 KOPPA is a scripting language built for penetration testers.
 It provides built-in modules for port scanning, DNS recon,
 HTTP probing, cryptographic operations, and file I/O.
EOF

# ── postinst: set executable bit ─────────────────────────────────────────────
cat > "$BUILD_DIR/DEBIAN/postinst" <<'EOF'
#!/bin/sh
chmod +x /usr/local/bin/koppa
EOF
chmod 755 "$BUILD_DIR/DEBIAN/postinst"

# ── Install Python source ─────────────────────────────────────────────────────
cp -r "$ROOT/src/"*.py     "$BUILD_DIR/usr/local/lib/koppa/"
cp -r "$ROOT/stdlib/"*     "$BUILD_DIR/usr/local/lib/koppa/stdlib/" 2>/dev/null || true
cp -r "$ROOT/examples/"*.kop "$BUILD_DIR/usr/local/lib/koppa/examples/" 2>/dev/null || true
cp    "$ROOT/README.md"    "$BUILD_DIR/usr/share/doc/koppa/README.md" 2>/dev/null || true

# ── Launcher script ───────────────────────────────────────────────────────────
cat > "$BUILD_DIR/usr/local/bin/koppa" <<'EOF'
#!/usr/bin/env python3
import sys, os
sys.path.insert(0, "/usr/local/lib/koppa")
os.environ.setdefault("KOPPA_STDLIB", "/usr/local/lib/koppa/stdlib")
from koppa import main
main()
EOF
chmod 755 "$BUILD_DIR/usr/local/bin/koppa"

# ── Build .deb ────────────────────────────────────────────────────────────────
OUT="$ROOT/${PKG_NAME}.deb"
dpkg-deb --build "$BUILD_DIR" "$OUT"

echo ""
echo "[+] Built: $OUT"
echo ""
echo "Install with:"
echo "  sudo dpkg -i $OUT"
echo ""
echo "Remove with:"
echo "  sudo dpkg -r koppa"
