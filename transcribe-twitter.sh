#!/usr/bin/env bash
# Fetch an X/Twitter status: thread text, photos, optional video + Whisper.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/config-root.sh
source "${SCRIPT_DIR}/lib/config-root.sh"
VENV="${CONFIG_ROOT}/whisper-venv"
COOKIES="${HOME}/.config/x-cookies.txt"
PYTHON="${VENV}/bin/python3"
[[ -x "$PYTHON" ]] || PYTHON="python3"
MODEL="small"
FRAME_INTERVAL="${IG_REEL_FRAME_INTERVAL:-1}"

usage() {
  echo "Usage: $(basename "$0") <twitter-or-x-url> [--model small|medium] [--skip-whisper]" >&2
  echo "  Text + photos via FixTweet. Video via yt-dlp (optional ~/.config/x-cookies.txt)." >&2
  exit 1
}

SKIP_WHISPER=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --skip-whisper) SKIP_WHISPER=1; shift ;;
    -h|--help) usage ;;
    -*) echo "Unknown option: $1" >&2; usage ;;
    *)
      [[ -z "${URL:-}" ]] && URL="$1" || { echo "Unexpected: $1" >&2; usage; }
      shift
      ;;
  esac
done
[[ -n "${URL:-}" ]] || usage

# shellcheck source=lib/whisper-run.sh
source "${SCRIPT_DIR}/lib/whisper-run.sh"
# shellcheck source=lib/frame-extract.sh
source "${SCRIPT_DIR}/lib/frame-extract.sh"

if command -v ollama >/dev/null 2>&1 && [[ "$SKIP_WHISPER" -eq 0 ]]; then
  LOADED=$(ollama ps 2>/dev/null | tail -n +2 || true)
  if [[ -n "$LOADED" ]]; then
    echo "WARNING: Ollama models loaded — unload before long Whisper runs." >&2
    echo "$LOADED" >&2
  fi
fi

ID=$(python3 -c "import re,sys; m=re.search(r'(?:status|statuses)/(\\d+)', sys.argv[1]); print(m.group(1) if m else '')" "$URL")
[[ -n "$ID" ]] || { echo "Could not parse tweet id from URL" >&2; exit 1; }
OUT="${CONFIG_ROOT}/downloads/twitter/${ID}"
mkdir -p "$OUT"

echo "[1/4] Fetching tweet + thread (FixTweet)..." >&2
META=$("$PYTHON" "${SCRIPT_DIR}/lib/twitter-fetch.py" "$URL" "$OUT")
ID=$(printf '%s' "$META" | cut -f1)
HANDLE=$(printf '%s' "$META" | cut -f2)
PHOTO_COUNT=$(printf '%s' "$META" | cut -f3)
HAS_VIDEO=$(printf '%s' "$META" | cut -f4)
echo "      ID: $ID  @${HANDLE}  photos: ${PHOTO_COUNT}  video_flag: ${HAS_VIDEO}" >&2

VIDEO=""
YTDLP=(yt-dlp)
if [[ -f "$COOKIES" ]]; then
  YTDLP+=(--cookies "$COOKIES")
fi

echo "[2/4] Trying yt-dlp for video..." >&2
if "${YTDLP[@]}" --print id "$URL" >/dev/null 2>&1; then
  VIDEO=$("${YTDLP[@]}" \
    -o "${OUT}/${ID}.%(ext)s" \
    --print after_move:filepath \
    "$URL" 2>"${OUT}/${ID}.ytdlp.log" || true)
  if [[ -n "${VIDEO:-}" && -f "$VIDEO" ]]; then
    echo "      Video: $VIDEO" >&2
    HAS_VIDEO=1
  else
    VIDEO=""
    echo "      No video file (text/photos only, or login wall — export cookies to $COOKIES)" >&2
  fi
else
  echo "      yt-dlp could not resolve media (ok for text/photo tweets)." >&2
fi

TXT="${OUT}/${ID}.txt"
# Combined file is written last via a temp. Never cat $TXT into itself —
# whisper_transcribe writes ${audio_basename}.txt; if audio is ${ID}.m4a
# that IS $TXT, and `{ cat $TXT; } > $TXT` grew to 90GB (2026-08-18).
cp "$OUT/thread.txt" "$TXT"

if [[ -n "$VIDEO" && "$SKIP_WHISPER" -eq 0 ]]; then
  duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$VIDEO")
  duration_int=${duration%%.*}
  # Long tweet-videos are usually the author reading the thread. Thread is SoT.
  if [[ "${duration_int:-0}" -gt 180 ]]; then
    echo "[3/4] Skip Whisper (video ${duration_int}s > 180s; thread.txt is source of truth)." >&2
  else
    # Sidecar name so Whisper cannot clobber $TXT
    AUDIO="${OUT}/${ID}.audio.m4a"
    echo "[3/4] Audio + frames + Whisper..." >&2
    if ! ffmpeg -y -i "$VIDEO" -vn -acodec aac -b:a 128k "$AUDIO" -loglevel error; then
      echo "      Audio extract failed — thread.txt stays source of truth" >&2
      AUDIO=""
    fi
    FRAME_COUNT=0
    if [[ "${duration_int:-0}" -le 120 ]]; then
      frame_extract "$VIDEO" "${OUT}/frames" "$FRAME_INTERVAL" || true
      echo "      Frames: $FRAME_COUNT" >&2
    else
      echo "      Frames skipped (>120s). Use reextract-frames.sh ${ID}" >&2
    fi
    WHISPER_OUT=""
    if [[ -n "$AUDIO" && -f "$AUDIO" ]]; then
      WHISPER_OUT=$(whisper_transcribe "$AUDIO" "$OUT" "$MODEL" | tail -1)
    fi
    if [[ -n "${WHISPER_OUT:-}" && -f "$WHISPER_OUT" && "$WHISPER_OUT" != "$TXT" ]]; then
      tmp=$(mktemp)
      {
        echo "=== Tweet / thread ==="
        cat "$OUT/thread.txt"
        echo ""
        echo "=== Video transcript ==="
        cat "$WHISPER_OUT"
      } > "$tmp"
      mv "$tmp" "$TXT"
    fi
  fi
else
  echo "[3/4] Skip Whisper (no video or --skip-whisper)." >&2
fi

OCR_DIRS=()
[[ -d "$OUT/photos" ]] && OCR_DIRS+=(--dir "$OUT/photos")
[[ -d "$OUT/frames" ]] && OCR_DIRS+=(--dir "$OUT/frames")
if [[ ${#OCR_DIRS[@]} -gt 0 ]]; then
  bash "${SCRIPT_DIR}/lib/ocr-frames.sh" "${OCR_DIRS[@]}" --out "${OUT}/${ID}.ocr.txt" || true
fi

echo "[4/4] Done." >&2
echo "--- Summary ---" >&2
echo "ID:       $ID" >&2
echo "Handle:   @$HANDLE" >&2
echo "Thread:   $OUT/thread.txt" >&2
echo "Photos:   $OUT/photos/ ($PHOTO_COUNT)" >&2
[[ -n "$VIDEO" ]] && echo "Video:    $VIDEO" >&2
echo "Combined: $TXT" >&2
# Thread only — never dump a huge combined file to stdout (filled the disk once).
cat "$OUT/thread.txt"
