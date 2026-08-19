"""Remove old raw media from downloads/; keep transcripts and metadata."""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

from local_config import default_vault, downloads_dir


KEEP_SUFFIXES = {".txt", ".log"}
DELETE_SUFFIXES = {
    ".mp4",
    ".m4a",
    ".jpg",
    ".jpeg",
    ".webp",
    ".png",
    ".srt",
    ".vtt",
}
# Keep transcripts even when suffix is .txt; deletable includes .subs.log via name
DELETE_NAMES_EXTRA = {".subs.log"}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="igx cleanup",
        description="Delete old media; keep *.txt, *.description.txt, *.ocr.txt, *.whisper.log",
    )
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--keep-noted",
        action="store_true",
        help="Skip IDs that appear in an Obsidian vault filename",
    )
    return p


def _older_than(path: Path, days: int) -> bool:
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age > days * 86400


def _vault_ids(vault: Path) -> set[str]:
    names: set[str] = set()
    if not vault.is_dir():
        return names
    for path in vault.rglob("*.md"):
        names.add(path.stem)
        names.add(path.name)
    return names


def _noted(mid: str, vault_names: set[str]) -> bool:
    if not mid:
        return False
    for name in vault_names:
        if mid in name:
            return True
    return False


def _delete(path: Path, *, dry_run: bool) -> None:
    if dry_run:
        try:
            size = path.stat().st_size if path.is_file() else 0
        except OSError:
            size = 0
        print(f"would delete: {path} ({size} bytes)", file=sys.stderr)
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink(missing_ok=True)


def _is_deletable_file(name: str) -> bool:
    lower = name.lower()
    if lower.endswith(".subs.log"):
        return True
    suffix = Path(name).suffix.lower()
    if suffix in {".txt", ".log"}:
        return False
    return suffix in DELETE_SUFFIXES


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    download_dir = downloads_dir()
    if not download_dir.is_dir():
        print(f"Nothing to clean: {download_dir}", file=sys.stderr)
        return 0
    vault_names: set[str] = set()
    if args.keep_noted:
        vault_names = _vault_ids(default_vault())
    skipped = 0
    deleted = 0

    def skip_id(mid: str) -> bool:
        nonlocal skipped
        if args.keep_noted and _noted(mid, vault_names):
            skipped += 1
            return True
        return False

    for subdir in download_dir.glob("*"):
        if not subdir.is_dir() or subdir.name in {"youtube", "twitter"}:
            continue
        for kind in ("frames", "slides"):
            target = subdir / kind
            if target.is_dir() and _older_than(target, args.days):
                if skip_id(subdir.name):
                    continue
                _delete(target, dry_run=args.dry_run)
                deleted += 1
                if not args.dry_run and subdir.is_dir() and not any(subdir.iterdir()):
                    subdir.rmdir()

    for path in download_dir.iterdir():
        if not path.is_file() or not _older_than(path, args.days):
            continue
        mid = path.name.split(".", 1)[0]
        if skip_id(mid):
            continue
        if _is_deletable_file(path.name):
            _delete(path, dry_run=args.dry_run)
            deleted += 1

    youtube_dir = download_dir / "youtube"
    if youtube_dir.is_dir():
        for path in youtube_dir.iterdir():
            if not path.is_file() or not _older_than(path, args.days):
                continue
            mid = path.name.split(".", 1)[0]
            if skip_id(mid):
                continue
            if _is_deletable_file(path.name):
                _delete(path, dry_run=args.dry_run)
                deleted += 1

    twitter_dir = download_dir / "twitter"
    if twitter_dir.is_dir():
        for iddir in twitter_dir.iterdir():
            if not iddir.is_dir():
                continue
            for path in iddir.iterdir():
                if not _older_than(path, args.days):
                    continue
                if skip_id(iddir.name):
                    continue
                if path.is_dir() and path.name in {"photos", "frames"}:
                    _delete(path, dry_run=args.dry_run)
                    deleted += 1
                elif path.is_file() and _is_deletable_file(path.name):
                    _delete(path, dry_run=args.dry_run)
                    deleted += 1

    if args.dry_run:
        print(
            f"Dry run complete. {deleted} item(s) listed; {skipped} skipped (--keep-noted).",
            file=sys.stderr,
        )
    else:
        print(
            f"Cleanup done (media older than {args.days}d). Removed {deleted} item(s); skipped {skipped} noted reel(s).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
