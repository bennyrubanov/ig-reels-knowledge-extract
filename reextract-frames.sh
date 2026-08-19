#!/usr/bin/env bash
# Re-extract frames from an already-downloaded reel (no re-download, no re-transcribe).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/config-root.sh
source "${SCRIPT_DIR}/lib/config-root.sh"
DOWNLOAD_DIR="${CONFIG_ROOT}/downloads"
FRAME_INTERVAL="${IG_REEL_FRAME_INTERVAL:-1}"

usage() {
  echo "Usage: $(basename "$0") <reel-id> [--frame-interval SEC|auto|scene]" >&2
  echo "  Replaces downloads/{id}/frames/*.jpg using existing downloads/{id}.mp4" >&2
  exit 1
}

[[ $# -ge 1 ]] || usage

ID="$1"
shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    --frame-interval) FRAME_INTERVAL="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

VIDEO="${DOWNLOAD_DIR}/${ID}.mp4"
FRAMES_DIR="${DOWNLOAD_DIR}/${ID}/frames"

if [[ ! -f "$VIDEO" ]]; then
  echo "Video not found: $VIDEO" >&2
  echo "Run transcribe-reel.sh first, or pass the correct reel ID." >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/frame-extract.sh
source "${SCRIPT_DIR}/lib/frame-extract.sh"

rm -rf "$FRAMES_DIR"
FRAME_COUNT=0
frame_extract "$VIDEO" "$FRAMES_DIR" "$FRAME_INTERVAL"

if [[ -d "$FRAMES_DIR" ]]; then
  bash "${SCRIPT_DIR}/lib/ocr-frames.sh" --dir "$FRAMES_DIR" --out "${DOWNLOAD_DIR}/${ID}.ocr.txt" || true
fi

echo "--- Re-extract summary ---" >&2
echo "Reel ID:    $ID" >&2
echo "Video:      $VIDEO" >&2
echo "Frames:     $FRAME_COUNT in $FRAMES_DIR" >&2
echo "Interval:   $FRAME_INTERVAL" >&2
echo "OCR:        ${DOWNLOAD_DIR}/${ID}.ocr.txt" >&2
