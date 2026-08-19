#!/usr/bin/env python3
"""local_config loads gitignored overrides without baking them into git."""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from local_config import config_root, default_vault, parse_env_file, wanted_collections


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


if __name__ == "__main__":
    unittest.main()
