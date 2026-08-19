#!/usr/bin/env bash
# Thin wrapper — implementation is Python (Windows + Mac).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else echo "python3 not found" >&2; exit 1
fi
exec "$PY" "${SCRIPT_DIR}/scripts/igx.py" youtube "$@"
