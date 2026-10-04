import importlib.util
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

SCRIPT = Path(__file__).with_name("measure_trial14_pair.py")
spec = importlib.util.spec_from_file_location("measure_trial14_pair", SCRIPT)
measurements = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measurements)


class Trial14MeasurementTests(unittest.TestCase):
    def test_registration_and_four_dot_measurement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for ref, shift in (("D26", (2, 1)), ("D27", (0, 0))):
                before = Image.new("RGB", (1920, 1080), (0, 100, 180))
                px = before.load()
                # Textured fixed left patch makes the intended translation unique.
                for y in range(200, 700):
                    for x in range(100, 550):
                        g = (x * 17 + y * 23) % 150
                        px[x, y] = (0, g, 180)
                draw = ImageDraw.Draw(before)
                centers = ((871, 547), (1020, 545))
                for cx, cy in centers:
                    draw.rectangle((cx - 25, cy - 25, cx + 25, cy + 25), fill="white")

                after = Image.new("RGB", before.size, "black")
                after.paste(before, shift)
                dot_draw = ImageDraw.Draw(after)
                for cx, cy in centers:
                    dot_draw.ellipse((cx + shift[0] - 10 - 7, cy + shift[1] - 15 - 7,
                                      cx + shift[0] - 10 + 7, cy + shift[1] - 15 + 7), fill="black")

                before_path, after_path = root / f"{ref}-before.png", root / f"{ref}-after.png"
                before.save(before_path)
                after.save(after_path)
                if ref == "D26":
                    before_paths, after_paths = [before_path], [after_path]
                else:
                    before_paths.append(before_path)
                    after_paths.append(after_path)

            result = measurements.measure(before_paths, after_paths)
            self.assertEqual(result["registration"]["D26"]["translationPx"], [2, 1])
            self.assertEqual(result["registration"]["D27"]["translationPx"], [0, 0])
            self.assertEqual(len(result["pads"]), 4)
            for pad in result["pads"]:
                self.assertAlmostEqual(pad["offsetFromBeforeBrightPadCenterPx"][0], -10, delta=1)
                self.assertAlmostEqual(pad["offsetFromBeforeBrightPadCenterPx"][1], -15, delta=1)
                self.assertGreater(pad["projectedAreaMm2"], 0)
                self.assertGreater(pad["equivalentDiameterMm"], 0)
            self.assertFalse(result["pasteVolumeMeasured"])
            self.assertFalse(result["physicalAcceptanceEstablished"])


if __name__ == "__main__":
    unittest.main()
