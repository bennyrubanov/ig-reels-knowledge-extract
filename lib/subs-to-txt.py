#!/usr/bin/env python3
"""Convert SRT/VTT subtitle file to plain transcript text."""
import re
import sys
from pathlib import Path


def parse_srt(content: str) -> list[str]:
    lines = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        parts = block.strip().split("\n")
        if len(parts) < 2:
            continue
        # skip index line if numeric
        start = 1 if parts[0].strip().isdigit() else 0
        text_lines = []
        for line in parts[start:]:
            if re.match(r"\d{2}:\d{2}", line.strip()):
                continue
            cleaned = re.sub(r"<[^>]+>", "", line).strip()
            if cleaned:
                text_lines.append(cleaned)
        if text_lines:
            lines.append(" ".join(text_lines))
    return lines


def parse_vtt(content: str) -> list[str]:
    lines = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if re.match(r"\d{2}:\d{2}", line) or line.isdigit():
            continue
        if "-->" in line:
            continue
        cleaned = re.sub(r"<[^>]+>", "", line).strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: subs-to-txt.py INPUT.srt OUTPUT.txt", file=sys.stderr)
        sys.exit(1)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    content = src.read_text(encoding="utf-8", errors="replace")
    if src.suffix.lower() == ".vtt":
        parts = parse_vtt(content)
    else:
        parts = parse_srt(content)
    # dedupe consecutive identical lines (auto-caption overlap)
    out: list[str] = []
    prev = None
    for p in parts:
        if p != prev:
            out.append(p)
        prev = p
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(dst)


if __name__ == "__main__":
    main()
