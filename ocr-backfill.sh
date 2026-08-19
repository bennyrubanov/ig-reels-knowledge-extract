#!/usr/bin/env bash
# OCR every existing frames/slides/photos dir that does not yet have a sibling .ocr.txt
# Usage: ocr-backfill.sh [--force] [--jobs N]
set -euo pipefail

CONFIG_ROOT="${IG_REELS_ROOT:-${HOME}/.config/ig-reels-knowledge-extract}"
DOWNLOAD_DIR="${CONFIG_ROOT}/downloads"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FORCE=0
JOBS=6

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --jobs) JOBS="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $(basename "$0") [--force] [--jobs N]" >&2
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

ocr_one() {
  local dir="$1"
  local out="$2"
  if [[ "$FORCE" -eq 0 && -s "$out" ]]; then
    echo "skip  $out" >&2
    return 0
  fi
  echo "ocr   $dir → $out" >&2
  bash "${SCRIPT_DIR}/lib/ocr-frames.sh" --dir "$dir" --out "$out" --jobs "$JOBS"
}

# Instagram / generic: downloads/{id}/{frames,slides} → downloads/{id}.ocr.txt
while IFS= read -r -d '' iddir; do
  id="$(basename "$iddir")"
  case "$id" in youtube|twitter) continue ;; esac
  dirs=()
  [[ -d "${iddir}/frames" ]] && dirs+=(--dir "${iddir}/frames")
  [[ -d "${iddir}/slides" ]] && dirs+=(--dir "${iddir}/slides")
  [[ ${#dirs[@]} -gt 0 ]] || continue
  out="${DOWNLOAD_DIR}/${id}.ocr.txt"
  if [[ "$FORCE" -eq 0 && -s "$out" ]]; then
    echo "skip  $out" >&2
    continue
  fi
  echo "ocr   $id → $out" >&2
  bash "${SCRIPT_DIR}/lib/ocr-frames.sh" "${dirs[@]}" --out "$out" --jobs "$JOBS"
done < <(find "$DOWNLOAD_DIR" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)

# Twitter: downloads/twitter/{id}/{photos,frames} → downloads/twitter/{id}/{id}.ocr.txt
if [[ -d "${DOWNLOAD_DIR}/twitter" ]]; then
  while IFS= read -r -d '' iddir; do
    id="$(basename "$iddir")"
    dirs=()
    [[ -d "${iddir}/photos" ]] && dirs+=(--dir "${iddir}/photos")
    [[ -d "${iddir}/frames" ]] && dirs+=(--dir "${iddir}/frames")
    [[ ${#dirs[@]} -gt 0 ]] || continue
    out="${iddir}/${id}.ocr.txt"
    if [[ "$FORCE" -eq 0 && -s "$out" ]]; then
      echo "skip  $out" >&2
      continue
    fi
    echo "ocr   twitter $id → $out" >&2
    bash "${SCRIPT_DIR}/lib/ocr-frames.sh" "${dirs[@]}" --out "$out" --jobs "$JOBS"
  done < <(find "${DOWNLOAD_DIR}/twitter" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)
fi

# YouTube frames if anyone extracted them
if [[ -d "${DOWNLOAD_DIR}/youtube" ]]; then
  while IFS= read -r -d '' dir; do
    id="$(basename "$(dirname "$dir")")"
    ocr_one "$dir" "${DOWNLOAD_DIR}/youtube/${id}.ocr.txt"
  done < <(find "${DOWNLOAD_DIR}/youtube" -mindepth 2 -maxdepth 2 -type d -name frames -print0 2>/dev/null)
fi
