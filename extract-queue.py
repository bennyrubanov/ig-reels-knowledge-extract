#!/usr/bin/env python3
"""Shim — implementation lives in lib/extract_queue.py."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from extract_queue import main

if __name__ == "__main__":
    raise SystemExit(main())
