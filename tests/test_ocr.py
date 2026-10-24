"""Reads real screen captures of participant counts.  Run:  python -m unittest

Skipped if Tesseract isn't available. Add a capture by saving it in
tests/fixtures as count_<number>_<anything>.png.
"""

import re
import time
import unittest
from pathlib import Path

from PIL import Image

from endcall import ocr
from endcall.config import find_tesseract

FIXTURES = Path(__file__).parent / "fixtures"
TESSERACT = find_tesseract()


@unittest.skipUnless(TESSERACT, "Tesseract not found")
class ReadNumberTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ocr.use_tesseract(TESSERACT)

    def test_real_captures(self):
        files = sorted(FIXTURES.glob("count_*.png"))
        self.assertTrue(files, "no fixtures found")
        for path in files:
            expected = int(re.match(r"count_(\d+)", path.stem).group(1))
            with self.subTest(path.name):
                self.assertEqual(ocr.read_number(Image.open(path).convert("RGB")), expected)

    def test_fast_reader_agrees_and_reuses_results(self):
        reader = ocr.Reader()
        for path in sorted(FIXTURES.glob("count_*.png")):
            img = Image.open(path).convert("RGB")
            expected = int(re.match(r"count_(\d+)", path.stem).group(1))
            with self.subTest(path.name):
                self.assertEqual(reader.read(img), expected)
                start = time.perf_counter()
                self.assertEqual(reader.read(img), expected)  # same frame again
                self.assertLess(time.perf_counter() - start, 0.05)

    def test_blank_capture_reads_nothing(self):
        self.assertIsNone(ocr.read_number(Image.new("RGB", (50, 40), "white")))


if __name__ == "__main__":
    unittest.main()
