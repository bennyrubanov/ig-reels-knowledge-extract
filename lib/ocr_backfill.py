"""OCR every frames/slides/photos dir that does not yet have a sibling .ocr.txt."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from local_config import downloads_dir
from tooling import ocr_to_file


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="igx ocr-backfill")
    p.add_argument("--force", action="store_true")
    p.add_argument("--jobs", type=int, default=6)
    return p


def _ocr_one(dirs: list[Path], out: Path, *, force: bool, jobs: int) -> None:
    if not force and out.is_file() and out.stat().st_size > 0:
        print(f"skip  {out}", file=sys.stderr)
        return
    print(f"ocr   {dirs} → {out}", file=sys.stderr)
    ocr_to_file(*dirs, out=out, jobs=jobs)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    download_dir = downloads_dir()
    if not download_dir.is_dir():
        print(f"Nothing to OCR: {download_dir}", file=sys.stderr)
        return 0

    for iddir in download_dir.iterdir():
        if not iddir.is_dir() or iddir.name in {"youtube", "twitter"}:
            continue
        dirs = []
        if (iddir / "frames").is_dir():
            dirs.append(iddir / "frames")
        if (iddir / "slides").is_dir():
            dirs.append(iddir / "slides")
        if dirs:
            _ocr_one(dirs, download_dir / f"{iddir.name}.ocr.txt", force=args.force, jobs=args.jobs)

    twitter = download_dir / "twitter"
    if twitter.is_dir():
        for iddir in twitter.iterdir():
            if not iddir.is_dir():
                continue
            dirs = []
            if (iddir / "photos").is_dir():
                dirs.append(iddir / "photos")
            if (iddir / "frames").is_dir():
                dirs.append(iddir / "frames")
            if dirs:
                _ocr_one(
                    dirs,
                    iddir / f"{iddir.name}.ocr.txt",
                    force=args.force,
                    jobs=args.jobs,
                )

    youtube = download_dir / "youtube"
    if youtube.is_dir():
        for frames in youtube.glob("*/frames"):
            if frames.is_dir():
                mid = frames.parent.name
                _ocr_one(
                    [frames],
                    youtube / f"{mid}.ocr.txt",
                    force=args.force,
                    jobs=args.jobs,
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
