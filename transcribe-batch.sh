#!/usr/bin/env bash
# Process multiple URLs with safe parallelism. Scoreboard is disk + vault, not exit codes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MAX_JOBS="${MAX_JOBS:-2}"
JSONL="${EXTRACT_JSONL:-/tmp/extract.jsonl}"
URLS=()

usage() {
  echo "Usage: $(basename "$0") [--max-jobs N] [--jsonl FILE] URL [URL ...]" >&2
  echo "  Routes /reel/ /p/ YouTube X. Default MAX_JOBS=2. Audit: --jsonl (default /tmp/extract.jsonl)." >&2
  echo "  After the run, extract-status.sh is the scoreboard — do not count jsonl fail rows." >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-jobs) MAX_JOBS="$2"; shift 2 ;;
    --jsonl) JSONL="$2"; shift 2 ;;
    -h|--help) usage ;;
    -*) echo "Unknown: $1" >&2; usage ;;
    *) URLS+=("$1"); shift ;;
  esac
done

[[ ${#URLS[@]} -gt 0 ]] || usage

if command -v ollama >/dev/null 2>&1; then
  LOADED=$(ollama ps 2>/dev/null | tail -n +2 || true)
  if [[ -n "$LOADED" ]]; then
    echo "WARNING: Ollama loaded — use MAX_JOBS=1 or unload first." >&2
  fi
fi

exec python3 "${SCRIPT_DIR}/extract-queue.py" \
  --workers "$MAX_JOBS" \
  --jsonl "$JSONL" \
  "${URLS[@]}"
