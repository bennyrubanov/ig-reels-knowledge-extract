"""Download an Instagram reel, frames, optional Whisper."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from extract_status import media_id_from_url
from frame_extract import frame_extract
from local_config import downloads_dir, venv_python
from tooling import (
    extract_audio_aac,
    has_audio_stream,
    ocr_to_file,
    require_cmd,
    require_ig_cookies,
    warn_ollama,
    ytdlp,
    ytdlp_print,
)
from whisper_run import whisper_transcribe


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="igx reel",
        description="Download Instagram reel video, extract caption/frames, transcribe audio.",
    )
    p.add_argument("url")
    p.add_argument("-o", dest="output", help="Copy transcript to this path")
    p.add_argument("--model", default="small", choices=("small", "medium", "base"))
    p.add_argument(
        "--frame-interval",
        default=os.environ.get("IG_REEL_FRAME_INTERVAL", "1"),
        help="Seconds between frames, or auto|scene (default 1)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    cookies = require_ig_cookies()
    require_cmd("ffmpeg")
    if not venv_python().is_file():
        print(f"Whisper venv Python not found at {venv_python()} — run setup first.", file=sys.stderr)
        return 1
    warn_ollama()

    download_dir = downloads_dir()
    download_dir.mkdir(parents=True, exist_ok=True)

    mid = ytdlp_print("id", args.url, cookies=cookies)
    if not mid:
        mid = media_id_from_url(args.url)
    if not mid:
        print("Could not resolve reel id", file=sys.stderr)
        return 1

    description = download_dir / f"{mid}.description.txt"
    frames_dir = download_dir / mid / "frames"
    desc_proc = ytdlp(["--print", "description", args.url], cookies=cookies, capture=True)
    description.write_text(desc_proc.stdout or "", encoding="utf-8")

    dl = ytdlp(
        [
            "--write-thumbnail",
            "--convert-thumbnails",
            "jpg",
            "-o",
            str(download_dir / f"{mid}.%(ext)s"),
            "--print",
            "after_move:filepath",
            args.url,
        ],
        cookies=cookies,
        live_stderr=True,
    )
    video_s = (dl.stdout or "").strip().splitlines()
    video = Path(video_s[-1]) if video_s else download_dir / f"{mid}.mp4"
    if not video.is_file():
        print(f"Download failed — re-export cookies to {cookies} (docs/auth.md)", file=sys.stderr)
        return 1

    thumbnail = ""
    for ext in (".jpg", ".webp", ".png"):
        cand = download_dir / f"{mid}{ext}"
        if cand.is_file():
            thumbnail = str(cand)
            break

    audio = download_dir / f"{mid}.m4a"
    has_audio = 0
    if has_audio_stream(video):
        if extract_audio_aac(video, audio):
            has_audio = 1
        else:
            print("[transcribe] audio extract failed — continuing (video/frames still usable)", file=sys.stderr)
    else:
        print("[transcribe] no audio stream — skip Whisper", file=sys.stderr)

    result = frame_extract(video, frames_dir, args.frame_interval)
    if frames_dir.is_dir():
        ocr_to_file(frames_dir, out=download_dir / f"{mid}.ocr.txt")

    txt = download_dir / f"{mid}.txt"
    if has_audio and audio.is_file():
        print(
            f"[transcribe] faster-whisper (ETA below; log: {download_dir / (mid + '.whisper.log')})...",
            file=sys.stderr,
        )
        whisper_transcribe(audio, download_dir, args.model)

    if not txt.is_file():
        print("[transcribe] no transcript (music-only or Whisper skipped) — video/frames are enough to file", file=sys.stderr)

    if args.output and txt.is_file():
        Path(args.output).write_text(txt.read_text(encoding="utf-8"), encoding="utf-8")

    print("--- Summary ---", file=sys.stderr)
    print(f"Reel ID:       {mid}", file=sys.stderr)
    print(f"Description:   {description}", file=sys.stderr)
    print(f"Transcript:    {txt}", file=sys.stderr)
    print(f"Video:         {video}", file=sys.stderr)
    print(f"Frames:        {result.count} in {frames_dir}", file=sys.stderr)
    if thumbnail:
        print(f"Thumbnail:     {thumbnail}", file=sys.stderr)
    print("--- Transcript ---", file=sys.stderr)
    out = Path(args.output) if args.output else txt
    if out.is_file():
        sys.stdout.write(out.read_text(encoding="utf-8", errors="replace"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
