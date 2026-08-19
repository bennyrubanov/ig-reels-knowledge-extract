#!/usr/bin/env bash
# Canonical implementation: lib/frame_extract.py (python scripts/igx.py reextract …)
# This file is kept for older Mac notes that sourced it.
set -euo pipefail

# frame_extract VIDEO FRAMES_DIR INTERVAL
# INTERVAL: integer seconds, "auto", or "scene"
frame_extract() {
  local video="$1"
  local frames_dir="$2"
  local interval="$3"

  local duration duration_int
  duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$video")
  duration_int=${duration%%.*}

  mkdir -p "$frames_dir"
  FRAME_COUNT=0
  FRAME_MODE="fixed"
  FRAME_INTERVAL="$interval"

  _extract_at() {
    local ts="$1"
    local idx="$2"
    local outfile
    printf -v outfile "%s/frame_%03d.jpg" "$frames_dir" "$idx"
    # Limited-range YUV → mjpeg can exit 234 (ff_frame_thread_encoder_init).
    # Never fail the reel: skip the frame if both encodes die.
    if ffmpeg -y -ss "$ts" -i "$video" -frames:v 1 -q:v 2 -strict unofficial \
      "$outfile" -loglevel error && [[ -s "$outfile" ]]; then
      FRAME_COUNT=$((FRAME_COUNT + 1))
      return 0
    fi
    if ffmpeg -y -ss "$ts" -i "$video" -frames:v 1 -q:v 2 -vf "format=yuvj420p" \
      "$outfile" -loglevel error && [[ -s "$outfile" ]]; then
      FRAME_COUNT=$((FRAME_COUNT + 1))
      return 0
    fi
    echo "WARNING: skipped frame $idx at t=${ts}s (mjpeg/encode)" >&2
    return 0
  }

  _count_scenes() {
    ffmpeg -i "$video" -filter:v "select='gt(scene,0.35)',showinfo" -f null - 2>&1 \
      | grep -c 'Parsed_showinfo.* n:' || true
  }

  _pick_auto_interval() {
    local scenes="$1"
    local dur="$2"
    # Bias denser when unsure — prune raw media later via cleanup-downloads.sh.
    # Use 2s only for clearly static reels (very few scene cuts).
    if awk -v s="$scenes" -v d="$dur" 'BEGIN {
      rate = s / d
      exit !(rate >= 0.08 || s >= 3 || s >= d / 10)
    }'; then
      echo 1
    else
      echo 2
    fi
  }

  if [[ "$duration_int" -gt 120 ]]; then
    echo "Video longer than 120s (${duration_int}s) — skipping frame extraction." >&2
    return 0
  fi

  if [[ "$interval" == "auto" ]]; then
    local scenes
    scenes=$(_count_scenes)
    FRAME_INTERVAL=$(_pick_auto_interval "$scenes" "$duration_int")
    local rate
    rate=$(awk -v s="$scenes" -v d="$duration_int" 'BEGIN { printf "%.2f", s / d }')
    echo "Auto frame interval: ${FRAME_INTERVAL}s (${scenes} scene cuts in ${duration_int}s, ${rate} cuts/s)." >&2
  elif [[ "$interval" == "scene" ]]; then
    FRAME_MODE="scene"
    local idx=1
    while IFS= read -r ts; do
      [[ -n "$ts" ]] || continue
      _extract_at "$ts" "$idx"
      idx=$((idx + 1))
    done < <(
      ffmpeg -i "$video" -filter:v "select='gt(scene,0.35)',showinfo" -f null - 2>&1 \
        | grep 'pts_time:' \
        | sed -n 's/.*pts_time:\([0-9.]*\).*/\1/p'
    )
    # Always grab first frame; scene filter may skip t=0
    if [[ ! -f "${frames_dir}/frame_001.jpg" ]]; then
      _extract_at 0 1
    fi
    echo "Extracted $FRAME_COUNT scene-change frames (${duration_int}s video)." >&2
    return 0
  fi

  local idx=1 ts
  for ((ts = 0; ts <= duration_int; ts += FRAME_INTERVAL)); do
    _extract_at "$ts" "$idx"
    idx=$((idx + 1))
  done
  echo "Extracted $FRAME_COUNT frames every ${FRAME_INTERVAL}s (${duration_int}s video)." >&2
}
