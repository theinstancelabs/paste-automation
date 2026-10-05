import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock
from urllib.error import URLError

from automation.scripts import capture_viewer_usb_series as capture


class CaptureViewerSeriesTests(unittest.TestCase):
    def test_partial_capture_records_real_timestamps_and_explicit_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            token_path = root / "token"
            token_path.write_text("test-secret")
            output = root / "frames"
            argv = ["capture_viewer_usb_series.py", "--output", str(output),
                    "--sample-times", "0,0.01"]
            with mock.patch.object(capture, "TOKEN_PATH", token_path), \
                    mock.patch.object(capture, "fetch_frame", side_effect=[b"jpeg-bytes", URLError("offline")]), \
                    mock.patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(io.StringIO()):
                exit_code = capture.main()

            self.assertEqual(exit_code, 1)
            manifest_text = (output / "manifest.json").read_text()
            manifest = json.loads(manifest_text)
            self.assertEqual(manifest["status"], "partial")
            self.assertEqual(len(manifest["captures"]), 1)
            saved = manifest["captures"][0]
            self.assertEqual((output / saved["file"]).read_bytes(), b"jpeg-bytes")
            self.assertEqual(saved["status"], "saved")
            self.assertTrue(saved["captured_at_utc"].endswith("Z"))
            self.assertGreaterEqual(saved["elapsed_seconds"], 0)
            self.assertEqual(len(manifest["errors"]), 1)
            self.assertIn("URLError", manifest["errors"][0]["error"])
            self.assertNotIn("test-secret", manifest_text)

    def test_sample_times_must_be_strictly_increasing_and_bounded(self):
        self.assertEqual(capture.parse_sample_times("0,5,15,30,60"), [0, 5, 15, 30, 60])
        for invalid in ("5,0", "1,1", "3601", "-1"):
            with self.subTest(invalid=invalid), self.assertRaises(Exception):
                capture.parse_sample_times(invalid)


if __name__ == "__main__":
    unittest.main()
