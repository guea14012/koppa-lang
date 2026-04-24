#!/usr/bin/env bash
# KOPPA Language Installer for Linux / macOS
# Usage:
#   chmod +x install.sh
#   ./install.sh            # installs to ~/.local/bin (user)
#   sudo ./install.sh       # installs to /usr/local/bin (system)

set -e

KOPPA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CMD="$(command -v python3 || command -v python)"

if [ -z "$PYTHON_CMD" ]; then
    echo "[ERROR] Python 3.8+ is required. Install it first."
    exit 1
fi

PY_VER="$($PYTHON_CMD --version 2>&1 | awk '{print $2}')"
echo "[OK] Python $PY_VER found"

# Choose install prefix
if [ "$EUID" -eq 0 ]; then
    INSTALL_PREFIX="/usr/local"
    INSTALL_DIR="/usr/local/lib/koppa"
else
    INSTALL_PREFIX="$HOME/.local"
    INSTALL_DIR="$HOME/.local/lib/koppa"
fi

BIN_DIR="$INSTALL_PREFIX/bin"

echo "[  ] Installing to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR/src" "$INSTALL_DIR/stdlib" "$INSTALL_DIR/examples"

cp -r "$KOPPA_ROOT/src/"*     "$INSTALL_DIR/src/"
[ -d "$KOPPA_ROOT/stdlib" ]   && cp -r "$KOPPA_ROOT/stdlib/"*   "$INSTALL_DIR/stdlib/"   2>/dev/null || true
[ -d "$KOPPA_ROOT/examples" ] && cp -r "$KOPPA_ROOT/examples/"* "$INSTALL_DIR/examples/" 2>/dev/null || true

echo "[OK] Files copied"

# Create launcher script
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/koppa" << EOF
#!/usr/bin/env bash
export PYTHONPATH="$INSTALL_DIR/src:\$PYTHONPATH"
exec $PYTHON_CMD "$INSTALL_DIR/src/koppa.py" "\$@"
EOF
chmod +x "$BIN_DIR/koppa"
echo "[OK] Launcher created: $BIN_DIR/koppa"

# PATH hint
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo "[!] Add this to your shell profile to use 'koppa' from anywhere:"
    echo "    export PATH=\"\$PATH:$BIN_DIR\""
fi

echo ""
echo "============================================"
echo "  Installation complete!"
echo "============================================"
echo "  koppa version"
echo "  koppa run $INSTALL_DIR/examples/hello.kop"
echo "  koppa repl"
echo "============================================"
