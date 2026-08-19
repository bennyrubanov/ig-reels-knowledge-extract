#!/usr/bin/env bash
# OCR a frames/slides/photos directory → keep-forever .ocr.txt
# Usage: ocr-frames.sh --dir DIR [--dir DIR2] --out FILE [--jobs N]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DIRS=()
OUT=""
JOBS=6

usage() {
  echo "Usage: $(basename "$0") --dir DIR [--dir DIR] --out FILE [--jobs N]" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) DIRS+=("$2"); shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

[[ ${#DIRS[@]} -gt 0 && -n "$OUT" ]] || usage

args=()
for d in "${DIRS[@]}"; do
  args+=(--dir "$d")
done

python3 "${SCRIPT_DIR}/ocr_frames.py" "${args[@]}" --out "$OUT" --jobs "$JOBS" || {
  echo "WARNING: OCR failed — extract continues" >&2
  exit 0
}
