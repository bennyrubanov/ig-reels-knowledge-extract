#!/usr/bin/env bash
# Remove old raw media from downloads/; keep transcripts and metadata.
set -euo pipefail

CONFIG_ROOT="${IG_REELS_ROOT:-${HOME}/.config/ig-reels-knowledge-extract}"
DOWNLOAD_DIR="${CONFIG_ROOT}/downloads"
YOUTUBE_DIR="${DOWNLOAD_DIR}/youtube"
TWITTER_DIR="${DOWNLOAD_DIR}/twitter"
DAYS=30
DRY_RUN=0
KEEP_NOTED=0

usage() {
  cat <<'EOF' >&2
Usage: cleanup-downloads.sh [options]

  --days N       Delete media older than N days (default: 30)
  --dry-run      Print what would be deleted
  --keep-noted   Skip reel/video IDs that have a matching Obsidian note anywhere in the vault
  -h, --help     Show this help

Keeps:  *.txt, *.description.txt, *.ocr.txt, *.whisper.log (always)
Deletes: *.mp4, *.m4a, thumbnails, subtitle intermediates, {id}/frames/, {id}/slides/

Obsidian note match: any .md under OBSIDIAN_VAULT whose name contains the
reel/video ID (instagram/, youtube/, topic folders, wealth/investments/, …).
EOF
  exit 1
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -z "${OBSIDIAN_VAULT:-}" && -f "${SCRIPT_DIR}/local.env" ]]; then
  # shellcheck disable=SC1091
  set -a
  source "${SCRIPT_DIR}/local.env"
  set +a
fi
OBSIDIAN_VAULT="${OBSIDIAN_VAULT:-${HOME}/Documents/Obsidian}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --days) DAYS="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --keep-noted) KEEP_NOTED=1; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1" >&2; usage ;;
  esac
done

[[ -d "$DOWNLOAD_DIR" ]] || { echo "Nothing to clean: $DOWNLOAD_DIR" >&2; exit 0; }

_has_obsidian_note() {
  local id="$1"
  local match
  [[ -d "$OBSIDIAN_VAULT" ]] || return 1
  match=$(find "$OBSIDIAN_VAULT" -name "*${id}*" -name "*.md" -type f -print -quit 2>/dev/null || true)
  [[ -n "$match" ]]
}

_should_skip_id() {
  local id="$1"
  [[ "$KEEP_NOTED" -eq 1 ]] && _has_obsidian_note "$id"
}

_delete() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    du -sh "$1" 2>/dev/null | awk -v p="$1" '{print "would delete: " p " (" $1 ")"}'
  else
    rm -rf "$1"
  fi
}

_is_deletable_media() {
  case "$1" in
    *.mp4|*.m4a|*.jpg|*.jpeg|*.webp|*.png|*.srt|*.vtt|*.subs.log) return 0 ;;
    *) return 1 ;;
  esac
}

SKIPPED=0
DELETED=0

# Instagram media subdirs: downloads/{id}/frames/ and downloads/{id}/slides/
while IFS= read -r -d '' subdir; do
  id=$(basename "$(dirname "$subdir")")
  if _should_skip_id "$id"; then
    SKIPPED=$((SKIPPED + 1))
    continue
  fi
  _delete "$subdir"
  DELETED=$((DELETED + 1))
  parent="$(dirname "$subdir")"
  if [[ "$DRY_RUN" -eq 0 ]] && [[ -d "$parent" ]] && [[ -z "$(ls -A "$parent" 2>/dev/null)" ]]; then
    rmdir "$parent" 2>/dev/null || true
  fi
done < <(find "$DOWNLOAD_DIR" -mindepth 2 -maxdepth 2 -type d \( -name 'frames' -o -name 'slides' \) -mtime +"$DAYS" -print0 2>/dev/null)

# Instagram root media files
while IFS= read -r -d '' path; do
  base=$(basename "$path")
  id="${base%%.*}"
  if _should_skip_id "$id"; then
    SKIPPED=$((SKIPPED + 1))
    continue
  fi
  if _is_deletable_media "$base"; then
    _delete "$path"
    DELETED=$((DELETED + 1))
  fi
done < <(find "$DOWNLOAD_DIR" -maxdepth 1 -type f -mtime +"$DAYS" -print0 2>/dev/null)

# YouTube media files: downloads/youtube/{id}.*
if [[ -d "$YOUTUBE_DIR" ]]; then
  while IFS= read -r -d '' path; do
    base=$(basename "$path")
    id="${base%%.*}"
    if _should_skip_id "$id"; then
      SKIPPED=$((SKIPPED + 1))
      continue
    fi
    if _is_deletable_media "$base"; then
      _delete "$path"
      DELETED=$((DELETED + 1))
    fi
  done < <(find "$YOUTUBE_DIR" -maxdepth 1 -type f -mtime +"$DAYS" -print0 2>/dev/null)
fi

# Twitter: downloads/twitter/{id}/*
if [[ -d "$TWITTER_DIR" ]]; then
  while IFS= read -r -d '' path; do
    id=$(basename "$(dirname "$path")")
    if _should_skip_id "$id"; then
      SKIPPED=$((SKIPPED + 1))
      continue
    fi
    base=$(basename "$path")
    if _is_deletable_media "$base" || [[ "$base" == "photos" || "$base" == "frames" ]]; then
      _delete "$path"
      DELETED=$((DELETED + 1))
    fi
  done < <(find "$TWITTER_DIR" -mindepth 2 -maxdepth 2 \( -type f -o -type d \) -mtime +"$DAYS" -print0 2>/dev/null)
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry run complete. $DELETED item(s) listed; $SKIPPED skipped (--keep-noted)." >&2
else
  echo "Cleanup done (media older than ${DAYS}d). Removed $DELETED item(s); skipped $SKIPPED noted reel(s)." >&2
fi
