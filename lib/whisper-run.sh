# Canonical implementation: lib/whisper_run.py
# Shared transcription: faster-whisper (default) or openai-whisper (fallback).
# Usage: source this file, then whisper_transcribe AUDIO OUTPUT_DIR [model]

if [[ -z "${CONFIG_ROOT:-}" ]]; then
  _here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=config-root.sh
  source "${_here}/config-root.sh"
fi

whisper_transcribe() {
  local audio="$1"
  local out_dir="$2"
  local model="${3:-small}"
  local venv="${VENV:-${CONFIG_ROOT}/whisper-venv}"
  local backend="${WHISPER_BACKEND:-faster}"
  local root="${SCRIPT_DIR:-${CONFIG_ROOT}}"
  local lib_dir="${root}/lib"

  local python_bin="${venv}/bin/python3"
  [[ -x "$python_bin" ]] || python_bin="${venv}/bin/python"
  local whisper_bin="${venv}/bin/whisper"
  local fw_script="${lib_dir}/faster_whisper_transcribe.py"

  if [[ ! -f "$audio" ]]; then
    echo "ERROR: audio file not found: $audio" >&2
    return 1
  fi

  local base log duration_sec duration_min
  base=$(basename "$audio")
  base="${base%.*}"
  log="${out_dir}/${base}.whisper.log"
  mkdir -p "$out_dir"

  duration_sec=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$audio" 2>/dev/null || echo "0")
  duration_sec=${duration_sec%%.*}
  duration_min=$(( (duration_sec + 59) / 60 ))

  # RTF ballpark (Apple Silicon, 32 GB class):
  #   faster-whisper small int8: ~6.5x on long audio (4.6x on ~72s; model load)
  #   openai-whisper small:      ~2–3x
  local rtf=6 engine="faster-whisper"
  if [[ "$backend" == "openai" ]]; then
    engine="openai-whisper"
    rtf=3
    [[ "$model" == "medium" ]] && rtf=6
  else
    [[ "$model" == "medium" ]] && rtf=6
    [[ "$model" == "base" ]] && rtf=12
  fi

  local est_sec=$(( duration_sec / rtf + 20 ))
  [[ "$est_sec" -lt 15 ]] && est_sec=15
  local est_min=$(( (est_sec + 59) / 60 ))

  # Live list: lib/whisper-hotwords.txt (re-read every invoke so mid-batch edits apply).
  # A/B 2026-08-18 GEX: prompt cut GIMA 5→0, gamma 2→6. Hosting: SuperBase→Supabase, no leak.
  # Override: WHISPER_INITIAL_PROMPT=... WHISPER_HOTWORDS=...  Clear: WHISPER_HOTWORDS_FILE=/dev/null
  local hw_file="${WHISPER_HOTWORDS_FILE:-${root}/lib/whisper-hotwords.txt}"
  if [[ -z "${WHISPER_HOTWORDS+x}" || -z "${WHISPER_INITIAL_PROMPT+x}" ]]; then
    local hw_terms=""
    if [[ -f "$hw_file" ]]; then
      hw_terms=$(grep -v '^[[:space:]]*#' "$hw_file" | grep -v '^[[:space:]]*$' | paste -sd ', ' -)
    fi
    if [[ -z "${WHISPER_HOTWORDS+x}" ]]; then
      export WHISPER_HOTWORDS="$hw_terms"
    fi
    if [[ -z "${WHISPER_INITIAL_PROMPT+x}" ]]; then
      export WHISPER_INITIAL_PROMPT="$hw_terms"
    fi
  fi

  local t0
  t0=$(date +%s)

  {
    echo "=== Transcription ==="
    echo "Engine:    $engine"
    echo "Audio:     $audio"
    echo "Duration:  ${duration_min}m (${duration_sec}s)"
    echo "Model:     $model (expected RTF ~${rtf}x)"
    echo "Estimate:  ~${est_min}m (${est_sec}s wall clock)"
    echo "Log:       $log"
    echo "Started:   $(date '+%Y-%m-%d %H:%M:%S')"
    echo "---"
  } | tee "$log" >&2

  local txt="${out_dir}/${base}.txt"
  local ok=0

  if [[ "$backend" != "openai" ]]; then
    if [[ ! -f "$fw_script" ]]; then
      echo "WARNING: faster-whisper script missing ($fw_script) — falling back to openai-whisper" | tee -a "$log" >&2
    else
      set -o pipefail
      if "$python_bin" "$fw_script" "$audio" "$out_dir" "$model" 2>&1 | tee -a "$log"; then
        ok=1
      else
        echo "WARNING: faster-whisper failed — falling back to openai-whisper" | tee -a "$log" >&2
      fi
      set +o pipefail
    fi
  fi

  if [[ "$ok" -eq 0 ]]; then
    if [[ ! -x "$whisper_bin" ]]; then
      echo "ERROR: no transcription backend available" >&2
      return 1
    fi
    engine="openai-whisper (fallback)"
    if ! "$whisper_bin" "$audio" \
      --model "$model" --language en --output_format txt \
      --output_dir "$out_dir" --verbose True 2>&1 | tee -a "$log"; then
      echo "ERROR: whisper failed — see $log" >&2
      return 1
    fi
  fi

  local t1 elapsed elapsed_min actual_rtf=0
  t1=$(date +%s)
  elapsed=$(( t1 - t0 ))
  elapsed_min=$(( (elapsed + 59) / 60 ))
  if [[ "$duration_sec" -gt 0 && "$elapsed" -gt 0 ]]; then
    actual_rtf=$(( duration_sec / elapsed ))
    [[ "$actual_rtf" -lt 1 ]] && actual_rtf=1
  fi

  {
    echo "---"
    echo "Engine:    $engine"
    echo "Finished:  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Elapsed:   ${elapsed_min}m ${elapsed}s (${elapsed}s wall)"
    echo "RTF:       ~${actual_rtf}x (higher = faster than realtime)"
    echo "Transcript: $txt"
  } | tee -a "$log" >&2

  if [[ ! -f "$txt" ]]; then
    echo "ERROR: transcript not created at $txt" >&2
    return 1
  fi

  echo "$txt"
}
