#!/usr/bin/env bash
# Scoreboard for an extract jsonl: disk + vault, not raw fail counts.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "${SCRIPT_DIR}/lib/extract_status.py" "$@"
