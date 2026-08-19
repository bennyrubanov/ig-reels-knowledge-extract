#!/usr/bin/env bash
# Download Instagram reel video, extract caption/frames, transcribe audio with Whisper.
set -euo pipefail

COOKIES="${HOME}/.config/ig-cookies.txt"
CONFIG_ROOT="${IG_REELS_ROOT:-${HOME}/.config/ig-reels-knowledge-extract}"
VENV="${CONFIG_ROOT}/whisper-venv"
DOWNLOAD_DIR="${CONFIG_ROOT}/downloads"
MODEL="small"

usage() {
  echo "Usage: $(basename "$0") <instagram-reel-url> [-o output.txt] [--model small|medium] [--frame-interval SEC|auto|scene]" >&2
  echo "  --frame-interval N    Fixed seconds between frames (1 or 2)" >&2
  echo "  --frame-interval auto Pick 1s or 2s from scene cuts (biases 1s when unsure)" >&2
  echo "  --frame-interval scene Extract only on scene changes (+ t=0)" >&2
  echo "  Default: 1s. Env IG_REEL_FRAME_INTERVAL overrides (1|2|auto|scene)." >&2
  exit 1
}

OUTPUT=""
FRAME_INTERVAL="${IG_REEL_FRAME_INTERVAL:-1}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) OUTPUT="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --frame-interval) FRAME_INTERVAL="$2"; shift 2 ;;
    -h|--help) usage ;;
    -*) echo "Unknown option: $1" >&2; usage ;;
    *)
      if [[ -z "${URL:-}" ]]; then
        URL="$1"
      else
        echo "Unexpected argument: $1" >&2
        usage
      fi
      shift
      ;;
  esac
done

[[ -n "${URL:-}" ]] || usage

if [[ ! -f "$COOKIES" ]]; then
  echo "Cookie file missing: $COOKIES" >&2
  exit 1
fi

if [[ ! -x "${VENV}/bin/whisper" ]]; then
  echo "Whisper venv not found at $VENV — run setup first." >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg not found — required for audio/frame extraction." >&2
  exit 1
fi

mkdir -p "$DOWNLOAD_DIR"

# Warn if Ollama models loaded (non-blocking; agent rule handles interactive confirm)
if command -v ollama >/dev/null 2>&1; then
  LOADED=$(ollama ps 2>/dev/null | tail -n +2 || true)
  if [[ -n "$LOADED" ]]; then
    echo "WARNING: Ollama models loaded — Whisper uses ~2GB RAM. Unload with: ollama stop <model>" >&2
    echo "$LOADED" >&2
  fi
fi

ID=$(yt-dlp --cookies "$COOKIES" --print id "$URL")
DESCRIPTION_FILE="${DOWNLOAD_DIR}/${ID}.description.txt"
FRAMES_DIR="${DOWNLOAD_DIR}/${ID}/frames"
THUMBNAIL=""

yt-dlp --cookies "$COOKIES" --print description "$URL" > "$DESCRIPTION_FILE"

VIDEO=$(yt-dlp --cookies "$COOKIES" \
  --write-thumbnail --convert-thumbnails jpg \
  -o "${DOWNLOAD_DIR}/${ID}.%(ext)s" \
  --print after_move:filepath \
  "$URL")

if [[ ! -f "$VIDEO" ]]; then
  echo "Download failed — re-export cookies to $COOKIES" >&2
  exit 1
fi

for candidate in "${DOWNLOAD_DIR}/${ID}.jpg" "${DOWNLOAD_DIR}/${ID}.webp" "${DOWNLOAD_DIR}/${ID}.png"; do
  if [[ -f "$candidate" ]]; then
    THUMBNAIL="$candidate"
    break
  fi
done

AUDIO="${DOWNLOAD_DIR}/${ID}.m4a"
HAS_AUDIO=0
if ffprobe -v error -select_streams a:0 -show_entries stream=index -of csv=p=0 "$VIDEO" | grep -q .; then
  if ffmpeg -y -i "$VIDEO" -vn -acodec aac -b:a 128k "$AUDIO" -loglevel error; then
    HAS_AUDIO=1
  else
    echo "[transcribe] audio extract failed — continuing (video/frames still usable)" >&2
  fi
else
  echo "[transcribe] no audio stream — skip Whisper" >&2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/frame-extract.sh
source "${SCRIPT_DIR}/lib/frame-extract.sh"
FRAME_COUNT=0
if ! frame_extract "$VIDEO" "$FRAMES_DIR" "$FRAME_INTERVAL"; then
  echo "[transcribe] frame extract failed — video/caption still usable" >&2
fi
if [[ -d "$FRAMES_DIR" ]]; then
  bash "${SCRIPT_DIR}/lib/ocr-frames.sh" --dir "$FRAMES_DIR" --out "${DOWNLOAD_DIR}/${ID}.ocr.txt" || true
fi

TXT="${DOWNLOAD_DIR}/${ID}.txt"
# shellcheck source=lib/whisper-run.sh
source "${SCRIPT_DIR}/lib/whisper-run.sh"

if [[ "$HAS_AUDIO" -eq 1 && -f "$AUDIO" ]]; then
  echo "[transcribe] faster-whisper (ETA below; log: ${DOWNLOAD_DIR}/${ID}.whisper.log)..." >&2
  whisper_transcribe "$AUDIO" "$DOWNLOAD_DIR" "$MODEL" >/dev/null || true
fi

if [[ ! -f "$TXT" ]]; then
  echo "[transcribe] no transcript (music-only or Whisper skipped) — video/frames are enough to file" >&2
fi

if [[ -n "$OUTPUT" ]]; then
  cp "$TXT" "$OUTPUT"
fi

echo "--- Summary ---" >&2
echo "Reel ID:       $ID" >&2
echo "Description:   $DESCRIPTION_FILE" >&2
echo "Transcript:    $TXT" >&2
echo "Video:         $VIDEO" >&2
echo "Frames:        $FRAME_COUNT in $FRAMES_DIR" >&2
if [[ -n "$THUMBNAIL" ]]; then
  echo "Thumbnail:     $THUMBNAIL" >&2
fi
echo "--- Transcript ---" >&2

if [[ -n "$OUTPUT" && -f "$OUTPUT" ]]; then
  cat "$OUTPUT"
elif [[ -f "$TXT" ]]; then
  cat "$TXT"
fi
