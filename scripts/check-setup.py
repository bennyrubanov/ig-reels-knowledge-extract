#!/usr/bin/env python3
"""Local setup check for agents and humans. Never prints cookie values."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from local_config import (  # noqa: E402
    config_root,
    ig_cookies_path,
    venv_whisper,
    x_cookies_path,
)

HOME = Path.home()
COOKIES = ig_cookies_path()
X_COOKIES = x_cookies_path()
SYMLINKS = (
    HOME / ".config" / "ig-yt-x-knowledge-extract",
    HOME / ".config" / "ig-reels-knowledge-extract",
    HOME / ".config" / "ig-reel",
)


def ok(msg: str) -> None:
    print(f"ok   {msg}")


def bad(msg: str) -> None:
    print(f"FAIL {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    print(f"warn {msg}")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def has_sessionid(path: Path) -> bool:
    """True if a Netscape row is named sessionid. Does not print the value."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    for line in text.splitlines():
        if not line.strip():
            continue
        # HttpOnly rows often start with #HttpOnly_.instagram.com
        if line.startswith("#") and not line.startswith("#HttpOnly_"):
            continue
        parts = line.split("\t")
        if len(parts) >= 6 and parts[5] == "sessionid":
            return True
    return False


def check_symlink() -> bool:
    for p in SYMLINKS:
        if p.exists():
            ok(f"config symlink {p}")
            return True
    warn("no ~/.config symlink — using this clone (normal on Windows)")
    return True


def check_cmds() -> bool:
    fine = True
    for name in ("yt-dlp", "ffmpeg", "ffprobe"):
        path = shutil.which(name)
        if path:
            ok(f"{name} -> {path}")
        else:
            bad(f"{name} not on PATH")
            fine = False
    if shutil.which("tesseract"):
        ok("tesseract (OCR)")
    else:
        warn("tesseract not on PATH — on-screen OCR skipped")
    return fine


def check_venv() -> bool:
    whisper = venv_whisper(config_root())
    if not whisper.is_file():
        whisper = venv_whisper(repo_root())
    if whisper.is_file():
        ok(f"whisper venv {whisper}")
        return True
    bad(f"whisper venv missing at {whisper} — README.md setup")
    return False


def check_cookies() -> bool:
    if not COOKIES.is_file():
        bad(f"missing {COOKIES}")
        print("     No Instagram OAuth. Export a Netscape jar. docs/auth.md", file=sys.stderr)
        return False
    if os.name != "nt":
        mode = COOKIES.stat().st_mode & 0o777
        if mode & 0o077:
            warn(f"{COOKIES} mode {mode:o} — chmod 600")
        else:
            ok(f"{COOKIES} mode {mode:o}")
    else:
        ok(f"{COOKIES} present")
    if has_sessionid(COOKIES):
        ok("ig-cookies.txt has a sessionid row (value not printed)")
        return True
    bad("ig-cookies.txt has no sessionid row — re-export HttpOnly; docs/auth.md")
    return False


def check_x_cookies() -> None:
    if X_COOKIES.is_file():
        ok(f"optional X jar present ({X_COOKIES})")
    else:
        warn(f"no {X_COOKIES} — X video may hit a login wall; text still works")


def check_vault() -> None:
    local = repo_root() / "local.env"
    if not local.is_file():
        warn("no local.env — copy local.env.example and set OBSIDIAN_VAULT")
        return
    vault = None
    for line in local.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("OBSIDIAN_VAULT="):
            vault = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not vault:
        warn("local.env has no OBSIDIAN_VAULT")
        return
    p = Path(vault)
    if p.is_dir():
        ok(f"OBSIDIAN_VAULT {p}")
    else:
        bad(f"OBSIDIAN_VAULT does not exist: {p}")


def check_ollama() -> None:
    if not shutil.which("ollama"):
        return
    try:
        out = subprocess.run(
            ["ollama", "ps"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return
    lines = [ln for ln in (out.stdout or "").splitlines()[1:] if ln.strip()]
    if lines:
        warn("ollama has a loaded model — Whisper also uses RAM")
        for ln in lines:
            print(f"     {ln}")


def main() -> int:
    print("ig-yt-x-knowledge-extract setup check")
    print("Auth recipe: docs/auth.md  (no Instagram OAuth)")
    fine = True
    fine &= check_symlink()
    fine &= check_cmds()
    fine &= check_venv()
    fine &= check_cookies()
    check_x_cookies()
    check_vault()
    check_ollama()
    if fine:
        print("ready. python scripts/igx.py reel URL  (Unix: transcribe-reel.sh)")
        return 0
    print("not ready. Fix FAIL lines. Do not paste cookie contents into chat.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
