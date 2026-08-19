#!/usr/bin/env python3
"""OCR on-screen text from frame/slide/photo JPEGs → a keep-forever .ocr.txt.

Storage is tiny next to the JPGs. Cleanup must keep this file when it deletes
frames/. Not a Whisper transcript and not as good as agent vision on charts —
it is the durable dump so you can audit overlays after the images are gone.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def list_images(*dirs: Path) -> list[Path]:
    found: list[Path] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                found.append(p)
    return sorted(found, key=lambda p: p.name)


def normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def tesseract_ocr(path: Path) -> str:
    exe = shutil.which("tesseract")
    if not exe:
        raise FileNotFoundError("tesseract not on PATH")
    proc = subprocess.run(
        [exe, str(path), "stdout", "-l", "eng", "--psm", "6"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return (proc.stdout or "").strip()


def render_document(
    rows: list[tuple[Path, str]],
    *,
    backend: str,
    generated: str | None = None,
) -> str:
    stamp = generated or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"# ocr  backend={backend}  generated={stamp}  images={len(rows)}",
        "# On-screen text only — not the spoken transcript.",
        "# Consecutive identical reads are marked [= previous].",
        "",
    ]
    prev = ""
    nonempty = 0
    for path, raw in rows:
        text = raw.strip()
        norm = normalize_text(text)
        lines.append(f"## {path.name}")
        if not norm:
            lines.append("(no text)")
        elif norm == prev:
            lines.append("[= previous]")
        else:
            lines.append(text)
            nonempty += 1
            prev = norm
        lines.append("")
    lines.append(f"# summary  nonempty={nonempty}  blank_or_dup={len(rows) - nonempty}")
    lines.append("")
    return "\n".join(lines)


def ocr_images(
    images: list[Path],
    ocr_one: Callable[[Path], str] = tesseract_ocr,
    jobs: int = 6,
) -> list[tuple[Path, str]]:
    if not images:
        return []
    workers = max(1, min(jobs, len(images)))
    results: dict[Path, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(ocr_one, p): p for p in images}
        for fut in as_completed(futs):
            p = futs[fut]
            try:
                results[p] = fut.result()
            except Exception as exc:  # noqa: BLE001 — keep the extract job alive
                results[p] = f"(ocr failed: {exc})"
    return [(p, results[p]) for p in images]


def write_ocr(
    *dirs: Path,
    out: Path,
    ocr_one: Callable[[Path], str] = tesseract_ocr,
    jobs: int = 6,
    backend: str = "tesseract",
) -> Path:
    images = list_images(*dirs)
    rows = ocr_images(images, ocr_one=ocr_one, jobs=jobs)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_document(rows, backend=backend), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="OCR frames/slides/photos to a keep-forever .ocr.txt")
    p.add_argument("--dir", action="append", type=Path, required=True, dest="dirs")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--jobs", type=int, default=6)
    args = p.parse_args(argv)
    if not shutil.which("tesseract"):
        print("WARNING: tesseract not on PATH — skip OCR", flush=True)
        return 0
    path = write_ocr(*args.dirs, out=args.out, jobs=args.jobs)
    print(f"OCR: {path} ({path.stat().st_size} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
