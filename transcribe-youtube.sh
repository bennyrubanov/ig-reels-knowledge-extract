#!/usr/bin/env bash
# Download YouTube: native captions first (fast), else faster-whisper with ETA + progress log.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/config-root.sh
source "${SCRIPT_DIR}/lib/config-root.sh"
VENV="${CONFIG_ROOT}/whisper-venv"
DOWNLOAD_DIR="${CONFIG_ROOT}/downloads/youtube"
MODEL="small"
PYTHON="${VENV}/bin/python3"

usage() {
  echo "Usage: $(basename "$0") <youtube-url> [--model small|medium] [--force-whisper] [-o output.txt]" >&2
  echo "  Captions tried first (~15-30s). Whisper uses faster-whisper + ${MODEL}.whisper.log" >&2
  echo "  --force-whisper  Run Whisper anyway; writes ${ID}.whisper.txt (keeps caption .txt)" >&2
  exit 1
}

OUTPUT=""
FORCE_WHISPER=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o) OUTPUT="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --force-whisper) FORCE_WHISPER=1; shift ;;
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

if command -v ollama >/dev/null 2>&1; then
  LOADED=$(ollama ps 2>/dev/null | tail -n +2 || true)
  if [[ -n "$LOADED" ]]; then
    echo "WARNING: Ollama models loaded — unload before long Whisper runs." >&2
    echo "$LOADED" >&2
  fi
fi

mkdir -p "$DOWNLOAD_DIR"
PIPELINE_START=$(date +%s)

echo "[1/4] Resolving video..." >&2
ID=$(yt-dlp --print id "$URL")
TITLE=$(yt-dlp --print title "$URL")
DESC_FILE="${DOWNLOAD_DIR}/${ID}.description.txt"
yt-dlp --print description "$URL" > "$DESC_FILE"
echo "      ID: $ID" >&2
echo "      Title: $TITLE" >&2

echo "[2/4] Checking for native captions (en)..." >&2
SUB_START=$(date +%s)
SUB_FILE=""
SUB_LOG="${DOWNLOAD_DIR}/${ID}.subs.log"

yt-dlp --write-subs --write-auto-subs \
  --sub-langs "en,en-US,en-GB,en.*" \
  --sub-format "srt/best,vtt/best" \
  --convert-subs srt \
  --skip-download \
  -o "${DOWNLOAD_DIR}/${ID}.%(ext)s" \
  "$URL" 2>&1 | tee "$SUB_LOG" || true

shopt -s nullglob
# Prefer creator-uploaded subs (en) over auto captions (en-en, en-orig, …)
SUB_KIND=""
for f in "${DOWNLOAD_DIR}/${ID}.en.srt" "${DOWNLOAD_DIR}/${ID}.en.vtt"; do
  if [[ -f "$f" ]]; then
    SUB_FILE="$f"
    SUB_KIND="manual"
    break
  fi
done
if [[ -z "$SUB_FILE" ]]; then
  for f in "${DOWNLOAD_DIR}/${ID}"*.en*.srt "${DOWNLOAD_DIR}/${ID}"*.srt \
           "${DOWNLOAD_DIR}/${ID}"*.en*.vtt "${DOWNLOAD_DIR}/${ID}"*.vtt; do
    [[ -f "$f" ]] && SUB_FILE="$f" && SUB_KIND="auto" && break
  done
fi
shopt -u nullglob

META="${DOWNLOAD_DIR}/${ID}.captions.meta"
if [[ -n "$SUB_FILE" ]]; then
  {
    echo "kind: ${SUB_KIND:-unknown}"
    echo "file: $(basename "$SUB_FILE")"
    echo "manual_track: en (creator upload when present)"
    echo "auto_tracks: en-en, en-orig, … (YouTube speech recognition)"
    echo "check: yt-dlp --list-subs URL  → 'Available subtitles' vs 'automatic captions'"
  } > "$META"
fi

SUB_ELAPSED=$(( $(date +%s) - SUB_START ))
TXT="${DOWNLOAD_DIR}/${ID}.txt"
AUDIO=""
SOURCE=""

if [[ -n "$SUB_FILE" && "$FORCE_WHISPER" -eq 0 ]]; then
  SOURCE="native-captions"
  echo "      Found captions (${SUB_KIND}) in ${SUB_ELAPSED}s: $SUB_FILE" >&2
  echo "      Skipping Whisper — converting subtitles to text..." >&2
  "$PYTHON" "${SCRIPT_DIR}/lib/subs-to-txt.py" "$SUB_FILE" "$TXT"
  {
    echo "=== Native captions (Whisper skipped) ==="
    echo "Kind: ${SUB_KIND}"
    echo "Source: $SUB_FILE"
    echo "Meta: $META"
    echo "Elapsed: ${SUB_ELAPSED}s"
    echo "Transcript: $TXT"
  } > "${DOWNLOAD_DIR}/${ID}.whisper.log"
elif [[ -n "$SUB_FILE" && "$FORCE_WHISPER" -eq 1 ]]; then
  SOURCE="native-captions+whisper"
  echo "      Found captions (${SUB_KIND}): $SUB_FILE — keeping as source of truth" >&2
  "$PYTHON" "${SCRIPT_DIR}/lib/subs-to-txt.py" "$SUB_FILE" "$TXT"
  echo "[3/4] --force-whisper: downloading audio for comparison pass..." >&2
  DL_START=$(date +%s)
  AUDIO=$(yt-dlp -x --audio-format m4a \
    -o "${DOWNLOAD_DIR}/${ID}.%(ext)s" \
    --print after_move:filepath "$URL")
  DL_ELAPSED=$(( $(date +%s) - DL_START ))
  echo "      Downloaded in ${DL_ELAPSED}s: $AUDIO" >&2
  CAPTIONS_BACKUP=$(mktemp)
  cp "$TXT" "$CAPTIONS_BACKUP"
  echo "      Transcribing → ${ID}.whisper.txt (captions unchanged in ${ID}.txt)..." >&2
  WHISPER_OUT=$(whisper_transcribe "$AUDIO" "$DOWNLOAD_DIR" "$MODEL" | tail -1)
  mv "$WHISPER_OUT" "${DOWNLOAD_DIR}/${ID}.whisper.txt"
  cp "$CAPTIONS_BACKUP" "$TXT"
  rm -f "$CAPTIONS_BACKUP"
  {
    echo "=== Captions (source of truth) + Whisper comparison ==="
    echo "Caption kind: ${SUB_KIND}"
    echo "Caption file: $SUB_FILE"
    echo "Captions txt: $TXT"
    echo "Whisper txt:  ${DOWNLOAD_DIR}/${ID}.whisper.txt"
    echo "Meta: $META"
  } >> "${DOWNLOAD_DIR}/${ID}.whisper.log"
else
  SOURCE="faster-whisper"
  echo "      No captions found in ${SUB_ELAPSED}s — downloading audio..." >&2
  DL_START=$(date +%s)
  AUDIO=$(yt-dlp -x --audio-format m4a \
    -o "${DOWNLOAD_DIR}/${ID}.%(ext)s" \
    --print after_move:filepath "$URL")
  DL_ELAPSED=$(( $(date +%s) - DL_START ))
  echo "      Downloaded in ${DL_ELAPSED}s: $AUDIO" >&2

  echo "[3/4] Transcribing (ETA printed below; log: ${ID}.whisper.log)..." >&2
  TXT=$(whisper_transcribe "$AUDIO" "$DOWNLOAD_DIR" "$MODEL")
fi

echo "[4/4] Done." >&2
PIPELINE_ELAPSED=$(( $(date +%s) - PIPELINE_START ))
echo "--- Summary ---" >&2
echo "Title:       $TITLE" >&2
echo "ID:          $ID" >&2
echo "Source:      $SOURCE" >&2
echo "Description: $DESC_FILE" >&2
echo "Transcript:  $TXT" >&2
[[ -f "${DOWNLOAD_DIR}/${ID}.whisper.txt" ]] && echo "Whisper cmp: ${DOWNLOAD_DIR}/${ID}.whisper.txt" >&2
[[ -f "$META" ]] && echo "Caption meta: $META" >&2
[[ -n "$AUDIO" ]] && echo "Audio:       $AUDIO" >&2
[[ -n "$SUB_FILE" ]] && echo "Captions:    $SUB_FILE" >&2
echo "Total wall:  ${PIPELINE_ELAPSED}s (~$(( (PIPELINE_ELAPSED + 59) / 60 ))m)" >&2

if [[ -n "$OUTPUT" ]]; then
  cp "$TXT" "$OUTPUT"
fi

cat "$TXT"
