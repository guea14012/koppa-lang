#!/usr/bin/env bash
# KOPPA Language Launcher (Linux / macOS)
# Usage:
#   chmod +x koppa.sh
#   ./koppa.sh run examples/hello.kop
#   ln -s "$(pwd)/koppa.sh" /usr/local/bin/koppa   # system-wide install

KOPPA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$KOPPA_ROOT/src:$PYTHONPATH"

PYTHON_CMD="python3"
command -v python3 >/dev/null 2>&1 || PYTHON_CMD="python"

exec "$PYTHON_CMD" "$KOPPA_ROOT/src/koppa.py" "$@"
