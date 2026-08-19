#!/usr/bin/env python3
"""local_config loads gitignored overrides without baking them into git."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from local_config import (
    REPO_ROOT,
    config_root,
    default_jsonl_path,
    default_vault,
    ig_cookies_path,
    parse_env_file,
    user_config_dir,
    venv_python,
    venv_whisper,
    wanted_collections,
)


class LocalConfigTests(unittest.TestCase):
    def test_config_root_env_wins(self) -> None:
        with patch.dict(os.environ, {"IG_REELS_ROOT": "/tmp/custom-extract-root"}):
            self.assertEqual(config_root(), Path("/tmp/custom-extract-root"))

    def test_parse_env_file(self) -> None:
        parsed = parse_env_file("# hi\nOBSIDIAN_VAULT=/tmp/vault\n")
        self.assertEqual(parsed["OBSIDIAN_VAULT"], "/tmp/vault")

    def test_default_vault_uses_local_env(self) -> None:
        vault = default_vault()
        self.assertTrue(str(vault))
        self.assertIsInstance(vault, Path)

    def test_wanted_collections_are_strings_when_present(self) -> None:
        names = wanted_collections()
        if names is not None:
            self.assertTrue(all(isinstance(n, str) and n for n in names))

    def test_cookies_live_under_home_config(self) -> None:
        self.assertEqual(user_config_dir(), Path.home() / ".config")
        self.assertEqual(ig_cookies_path(), Path.home() / ".config" / "ig-cookies.txt")

    def test_jsonl_default_is_os_temp_not_unix_tmp(self) -> None:
        import tempfile

        path = default_jsonl_path()
        self.assertEqual(path, Path(tempfile.gettempdir()) / "extract.jsonl")

    def test_config_root_falls_back_to_clone_when_no_symlink(self) -> None:
        missing = (Path("/no-such-igx-config-a"), Path("/no-such-igx-config-b"))
        env = {k: v for k, v in os.environ.items() if k != "IG_REELS_ROOT"}
        with patch.dict(os.environ, env, clear=True):
            with patch("local_config._CONFIG_CANDIDATES", missing):
                self.assertEqual(config_root(), REPO_ROOT)

    def test_venv_python_posix_layout(self) -> None:
        root = Path("/repo")
        with patch.object(os, "name", "posix"):
            self.assertEqual(
                venv_python(root),
                root / "whisper-venv" / "bin" / "python3",
            )

    def test_venv_python_windows_layout(self) -> None:
        root = Path("C:/repo")
        with patch.object(os, "name", "nt"):
            self.assertEqual(
                venv_python(root),
                root / "whisper-venv" / "Scripts" / "python.exe",
            )

    def test_venv_whisper_windows_layout(self) -> None:
        root = Path("C:/repo")
        with patch.object(os, "name", "nt"):
            self.assertEqual(
                venv_whisper(root),
                root / "whisper-venv" / "Scripts" / "whisper.exe",
            )


if __name__ == "__main__":
    unittest.main()
