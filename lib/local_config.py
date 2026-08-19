"""Local overrides that must not ship in git.

Reads `local.env` in the repo (gitignored), then process env wins.
Used for vault path and optional Notion inbox IDs — never cookies or tokens.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_ENV_PATH = REPO_ROOT / "local.env"
WANTED_PATH = REPO_ROOT / "wanted-collections.txt"
_CONFIG_CANDIDATES = (
    Path.home() / ".config/ig-yt-x-knowledge-extract",
    Path.home() / ".config/ig-reels-knowledge-extract",
    Path.home() / ".config/ig-reel",
)


def user_config_dir() -> Path:
    """~/.config on Mac/Linux and %USERPROFILE%\\.config on Windows."""
    return Path.home() / ".config"


def ig_cookies_path() -> Path:
    return user_config_dir() / "ig-cookies.txt"


def x_cookies_path() -> Path:
    return user_config_dir() / "x-cookies.txt"


def config_root() -> Path:
    """Install symlink, else the clone. IG_REELS_ROOT wins."""
    raw = os.environ.get("IG_REELS_ROOT", "").strip()
    if raw:
        return Path(raw)
    for path in _CONFIG_CANDIDATES:
        if path.exists():
            return path
    return REPO_ROOT


def venv_dir(root: Path | None = None) -> Path:
    return (root or config_root()) / "whisper-venv"


def venv_bin_dir(root: Path | None = None) -> Path:
    venv = venv_dir(root)
    scripts = venv / "Scripts"
    posix = venv / "bin"
    if scripts.is_dir():
        return scripts
    if posix.is_dir():
        return posix
    return scripts if os.name == "nt" else posix


def venv_python(root: Path | None = None) -> Path:
    bindir = venv_bin_dir(root)
    for name in ("python.exe", "python3.exe", "python3", "python"):
        cand = bindir / name
        if cand.is_file():
            return cand
    return bindir / ("python.exe" if os.name == "nt" else "python3")


def venv_whisper(root: Path | None = None) -> Path:
    bindir = venv_bin_dir(root)
    for name in ("whisper.exe", "whisper"):
        cand = bindir / name
        if cand.is_file():
            return cand
    return bindir / ("whisper.exe" if os.name == "nt" else "whisper")


def downloads_dir(root: Path | None = None) -> Path:
    return (root or config_root()) / "downloads"


def default_jsonl_path() -> Path:
    return Path(tempfile.gettempdir()) / "extract.jsonl"


def parse_env_file(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key:
            out[key] = val
    return out


def load_local_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    if LOCAL_ENV_PATH.is_file():
        merged.update(parse_env_file(LOCAL_ENV_PATH.read_text(encoding="utf-8")))
    for key, val in os.environ.items():
        if val:
            merged[key] = val
    return merged


def default_vault() -> Path:
    raw = load_local_env().get("OBSIDIAN_VAULT", "").strip()
    if raw:
        return Path(raw)
    return Path.home() / "Documents/Obsidian"


def notion_database_id() -> str:
    return load_local_env().get("NOTION_DATABASE_ID", "").strip()


def notion_data_source_id() -> str:
    return load_local_env().get("NOTION_DATA_SOURCE_ID", "").strip()


def wanted_collections() -> list[str] | None:
    """None means 'every collection in the dump'."""
    if not WANTED_PATH.is_file():
        return None
    names = []
    for raw in WANTED_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            names.append(line)
    return names or None
