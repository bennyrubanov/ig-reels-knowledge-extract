#!/usr/bin/env python3
"""Frame-interval picker matches the bash auto heuristic."""
from __future__ import annotations

import unittest
from pathlib import Path

from frame_extract import pick_auto_interval
from reextract_frames import output_dirs


class AutoIntervalTests(unittest.TestCase):
    def test_static_talking_head_uses_2s(self) -> None:
        self.assertEqual(pick_auto_interval(scenes=0, duration_s=30), 2)
        self.assertEqual(pick_auto_interval(scenes=1, duration_s=40), 2)

    def test_cuts_or_enough_scenes_use_1s(self) -> None:
        self.assertEqual(pick_auto_interval(scenes=3, duration_s=40), 1)
        self.assertEqual(pick_auto_interval(scenes=4, duration_s=20), 1)

    def test_zero_duration_uses_2s(self) -> None:
        self.assertEqual(pick_auto_interval(scenes=5, duration_s=0), 2)


class ReextractLayoutTests(unittest.TestCase):
    def test_instagram_layout(self) -> None:
        root = Path("/dl")
        frames, ocr = output_dirs(root / "AbC.mp4", "AbC", root)
        self.assertEqual(frames, root / "AbC" / "frames")
        self.assertEqual(ocr, root / "AbC.ocr.txt")

    def test_twitter_layout(self) -> None:
        root = Path("/dl")
        video = root / "twitter" / "123" / "123.mp4"
        frames, ocr = output_dirs(video, "123", root)
        self.assertEqual(frames, video.parent / "frames")
        self.assertEqual(ocr, video.parent / "123.ocr.txt")

    def test_youtube_layout(self) -> None:
        root = Path("/dl")
        video = root / "youtube" / "dQw.mp4"
        frames, ocr = output_dirs(video, "dQw", root)
        self.assertEqual(frames, video.parent / "dQw" / "frames")
        self.assertEqual(ocr, video.parent / "dQw.ocr.txt")


if __name__ == "__main__":
    unittest.main()
