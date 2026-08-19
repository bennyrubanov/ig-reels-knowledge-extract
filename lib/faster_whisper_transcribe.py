#!/usr/bin/env python3
"""Transcribe with faster-whisper; segment progress to stderr."""
import os
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 4:
        print(
            "Usage: faster_whisper_transcribe.py AUDIO OUTPUT_DIR MODEL",
            file=sys.stderr,
        )
        sys.exit(1)

    audio = sys.argv[1]
    out_dir = Path(sys.argv[2])
    model_size = sys.argv[3]
    base = Path(audio).stem
    txt_path = out_dir / f"{base}.txt"

    from faster_whisper import WhisperModel

    # auto: CUDA if available, else CPU (Apple Silicon — fast with int8)
    model = WhisperModel(model_size, device="auto", compute_type="int8")

    extra = {}
    prompt = os.environ.get("WHISPER_INITIAL_PROMPT", "").strip()
    hotwords = os.environ.get("WHISPER_HOTWORDS", "").strip()
    if prompt:
        extra["initial_prompt"] = prompt
    if hotwords:
        extra["hotwords"] = hotwords

    segments, info = model.transcribe(
        audio,
        language="en",
        vad_filter=True,
        beam_size=5,
        **extra,
    )

    print(f"Detected language: {info.language} (p={info.language_probability:.2f})", flush=True)

    lines: list[str] = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        ts = f"[{seg.start:06.1f}s -> {seg.end:06.1f}s]"
        print(f"{ts} {text}", file=sys.stderr, flush=True)
        lines.append(text)

    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str(txt_path))


if __name__ == "__main__":
    main()
