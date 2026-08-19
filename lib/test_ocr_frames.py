#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ocr_frames import list_images, normalize_text, render_document, write_ocr


class OcrFramesTests(unittest.TestCase):
    def test_list_and_dedup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "frames"
            d.mkdir()
            (d / "frame_001.jpg").write_bytes(b"x")
            (d / "frame_002.jpg").write_bytes(b"x")
            (d / "readme.txt").write_text("no")
            images = list_images(d)
            self.assertEqual([p.name for p in images], ["frame_001.jpg", "frame_002.jpg"])

            fake = {
                images[0]: "ASTS  $57.80",
                images[1]: "ASTS   $57.80",
            }
            doc = render_document(
                [(p, fake[p]) for p in images],
                backend="fake",
                generated="2026-08-18T00:00:00Z",
            )
            self.assertIn("## frame_001.jpg", doc)
            self.assertIn("ASTS  $57.80", doc)
            self.assertIn("[= previous]", doc)
            self.assertIn("nonempty=1", doc)
            self.assertEqual(normalize_text("ASTS   $57.80"), "ASTS $57.80")

    def test_write_ocr_blank_and_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "slides"
            d.mkdir()
            a = d / "slide_01.jpg"
            b = d / "slide_02.jpg"
            a.write_bytes(b"x")
            b.write_bytes(b"x")

            def fake(path: Path) -> str:
                if path.name.endswith("01.jpg"):
                    return ""
                raise RuntimeError("boom")

            out = Path(tmp) / "id.ocr.txt"
            write_ocr(d, out=out, ocr_one=fake, jobs=2, backend="fake")
            text = out.read_text()
            self.assertIn("(no text)", text)
            self.assertIn("(ocr failed: boom)", text)


if __name__ == "__main__":
    unittest.main()
