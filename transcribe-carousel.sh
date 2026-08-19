#!/usr/bin/env bash
# Download Instagram carousel post (instagram.com/p/...) — caption + all slides (images + videos).
set -euo pipefail

COOKIES="${HOME}/.config/ig-cookies.txt"
CONFIG_ROOT="${IG_REELS_ROOT:-${HOME}/.config/ig-reels-knowledge-extract}"
DOWNLOAD_DIR="${CONFIG_ROOT}/downloads"
VENV="${CONFIG_ROOT}/whisper-venv"
MODEL="small"

usage() {
  echo "Usage: $(basename "$0") <instagram-post-url> [--model small|medium] [--transcribe-videos]" >&2
  echo "  Supports carousel posts (instagram.com/p/...) — image slides + video slides." >&2
  echo "  --transcribe-videos  Run Whisper on video slides that have audio (default: off)" >&2
  exit 1
}

TRANSCRIBE_VIDEOS=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --transcribe-videos) TRANSCRIBE_VIDEOS=1; shift ;;
    -h|--help) usage ;;
    -*) echo "Unknown option: $1" >&2; usage ;;
    *)
      if [[ -z "${URL:-}" ]]; then URL="$1"; else echo "Unexpected: $1" >&2; usage; fi
      shift
      ;;
  esac
done

[[ -n "${URL:-}" ]] || usage

if [[ ! -f "$COOKIES" ]]; then
  echo "Cookie file missing: $COOKIES" >&2
  exit 1
fi

mkdir -p "$DOWNLOAD_DIR"

# Prefer the shortcode in the URL. --print id on an image-only carousel
# either exits 1 ("No video formats") or prints child slide ids.
ID=$(printf '%s\n' "$URL" | sed -n 's#.*instagram.com/[^/]*/\([^/?#]*\).*#\1#p')
if [[ -z "${ID}" ]]; then
  ID=$(yt-dlp --cookies "$COOKIES" --ignore-no-formats-error --print id "$URL" 2>/dev/null | head -1 || true)
fi
if [[ -z "${ID}" ]]; then
  echo "Could not resolve post id from $URL" >&2
  exit 1
fi
DESCRIPTION_FILE="${DOWNLOAD_DIR}/${ID}.description.txt"
SLIDES_DIR="${DOWNLOAD_DIR}/${ID}/slides"
MANIFEST="${SLIDES_DIR}/manifest.txt"

yt-dlp --cookies "$COOKIES" --print description "$URL" > "$DESCRIPTION_FILE" || true
if [[ ! -s "$DESCRIPTION_FILE" ]]; then
  echo "[carousel] description empty (common on image-only posts)" >&2
fi

mkdir -p "$SLIDES_DIR"

# Carousel = playlist. Image slides have no video format.
# Thumbnail-only FIRST (tested 2026-08-18: video-first + grep hid success;
# --skip-download got 11–12 JPGs on DaM_-hTFCeA, Da5k5eGEghT, DbP92xMj_lo).
echo "[carousel] Downloading slides to $SLIDES_DIR ..." >&2
yt-dlp --cookies "$COOKIES" \
  --yes-playlist \
  --ignore-no-formats-error \
  --skip-download \
  --write-thumbnail --convert-thumbnails jpg \
  -o "${SLIDES_DIR}/slide_%(playlist_index)02d.%(ext)s" \
  "$URL" 2>&1 | grep -E '^\[download\]|^ERROR|^WARNING|^\[info\]' || true

slide_n=$(find "$SLIDES_DIR" -maxdepth 1 -type f \( -name 'slide_*.jpg' -o -name 'slide_*.webp' -o -name 'slide_*.mp4' \) 2>/dev/null | wc -l | tr -d ' ')
if [[ "${slide_n:-0}" -eq 0 ]]; then
  echo "[carousel] No thumbnails — retrying full download (video slides) ..." >&2
  yt-dlp --cookies "$COOKIES" \
    --yes-playlist \
    --ignore-no-formats-error \
    --write-thumbnail --convert-thumbnails jpg \
    -o "${SLIDES_DIR}/slide_%(playlist_index)02d.%(ext)s" \
    "$URL" 2>&1 | grep -E '^\[download\]|^ERROR|^WARNING' || true
fi

# Rename .jpg thumbnails that landed without video (image-only slides)
shopt -s nullglob
for thumb in "$SLIDES_DIR"/slide_*.jpg "$SLIDES_DIR"/slide_*.webp; do
  base="${thumb%.*}"
  if [[ ! -f "${base}.mp4" ]] && [[ ! -f "${base}.m4a" ]]; then
    mv -f "$thumb" "${base}.jpg" 2>/dev/null || true
  fi
done

# Build manifest
{
  echo "# Carousel $ID"
  echo "# source: $URL"
  echo "# description: $DESCRIPTION_FILE"
  echo ""
  ls -1 "$SLIDES_DIR" 2>/dev/null | grep -v '^manifest.txt$' | sort
} > "$MANIFEST"

SLIDE_COUNT=$(find "$SLIDES_DIR" -maxdepth 1 -type f ! -name 'manifest.txt' | wc -l | tr -d ' ')

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -d "$SLIDES_DIR" ]]; then
  bash "${SCRIPT_DIR}/lib/ocr-frames.sh" --dir "$SLIDES_DIR" --out "${DOWNLOAD_DIR}/${ID}.ocr.txt" || true
fi

if [[ "$TRANSCRIBE_VIDEOS" -eq 1 ]] && [[ -x "${VENV}/bin/whisper" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  # shellcheck source=lib/whisper-run.sh
  source "${SCRIPT_DIR}/lib/whisper-run.sh"
  for video in "$SLIDES_DIR"/slide_*.mp4; do
    [[ -f "$video" ]] || continue
    base="${video%.mp4}"
    audio="${base}.m4a"
    txt="${base}.txt"
    ffmpeg -y -i "$video" -vn -acodec aac -b:a 128k "$audio" -loglevel error 2>/dev/null || continue
    whisper_transcribe "$audio" "$(dirname "$video")" "$MODEL" >/dev/null || true
    echo "Transcribed: $txt" >&2
  done
fi

echo "--- Carousel summary ---" >&2
echo "Post ID:      $ID" >&2
echo "Description:  $DESCRIPTION_FILE" >&2
echo "Slides:       $SLIDE_COUNT files in $SLIDES_DIR" >&2
echo "Manifest:     $MANIFEST" >&2
echo "--- Description ---" >&2
if [[ -s "$DESCRIPTION_FILE" ]]; then
  cat "$DESCRIPTION_FILE"
else
  echo "(no caption)"
fi

if [[ "${SLIDE_COUNT:-0}" -gt 0 ]]; then
  exit 0
fi
echo "ERROR: no slides downloaded for $ID" >&2
exit 1
