#!/usr/bin/env python3
"""igx dispatcher and extract_queue use Python, not bash."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IgxTests(unittest.TestCase):
    def test_help_lists_commands(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "igx.py"), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        combined = (proc.stdout or "") + (proc.stderr or "")
        for cmd in ("reel", "carousel", "youtube", "twitter", "batch", "reextract", "cleanup"):
            self.assertIn(cmd, combined)

    def test_unknown_command_exits_2(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "igx.py"), "not-a-command"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)


class ExtractQueueCmdTests(unittest.TestCase):
    def test_igx_cmd_is_this_python_not_bash(self) -> None:
        from extract_queue import igx_cmd

        cmd = igx_cmd("reel")
        self.assertEqual(cmd[0], sys.executable)
        self.assertTrue(cmd[1].endswith("igx.py") or cmd[1].endswith("igx.py"))
        self.assertEqual(cmd[2], "reel")
        self.assertFalse(any(part.endswith(".sh") for part in cmd))


if __name__ == "__main__":
    unittest.main()
