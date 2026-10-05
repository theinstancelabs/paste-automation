import importlib.util
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

SPEC = importlib.util.spec_from_file_location('offline_tip_growth', Path(__file__).with_name('offline_tip_growth.py'))
growth = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(growth)


class OfflineTipGrowthTests(unittest.TestCase):
    def images(self, root, extension=0, shift=0, frame_shift=None, width=64):
        baseline = Image.new('RGB', (width, 80), 'black')
        frame = Image.new('RGB', (width, 80), 'black')
        for image, end, frame_offset in ((baseline, 45, shift), (frame, 45 + extension,
                                                                    shift if frame_shift is None else frame_shift)):
            draw = ImageDraw.Draw(image)
            x = 29 + frame_offset
            draw.rectangle((x, 10, x + 2, end), fill=(160, 160, 160))
        base_path = root / 'baseline.png'
        frame_path = root / 'frame.png'
        baseline.save(base_path)
        frame.save(frame_path)
        return base_path, frame_path

    def test_reports_only_connected_incremental_growth(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            baseline, frame = self.images(root, extension=4)
            result = growth.analyze(baseline, frame, roi=(20, 5, 45, 75))
            self.assertEqual(result['decision'], 'growth')
            self.assertEqual(result['connected_extension_px'], 4)
            self.assertIn('does not mean clean', result['meaning'])

    def test_small_or_disconnected_change_is_not_growth(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            baseline, frame = self.images(root, extension=2)
            self.assertEqual(growth.analyze(baseline, frame, roi=(20, 5, 45, 75))['decision'], 'no-change')
            image = Image.open(frame).convert('RGB')
            ImageDraw.Draw(image).rectangle((29, 55, 31, 58), fill=(160, 160, 160))
            image.save(frame)
            result = growth.analyze(baseline, frame, roi=(20, 5, 45, 75))
            self.assertEqual(result['decision'], 'no-change')
            self.assertEqual(result['connected_extension_px'], 2)

    def test_misalignment_bad_roi_and_resolution_mismatch_require_inspection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            baseline, shifted = self.images(root, extension=5, frame_shift=3)
            self.assertEqual(growth.analyze(baseline, shifted, roi=(20, 5, 45, 75))['decision'], 'inspect')
            wrong_size = root / 'wrong-size.png'
            Image.new('RGB', (63, 80), 'black').save(wrong_size)
            self.assertEqual(growth.analyze(baseline, wrong_size, roi=(20, 5, 45, 75))['decision'], 'inspect')
            self.assertEqual(growth.analyze(baseline, shifted, roi=(60, 5, 70, 75))['decision'], 'inspect')


if __name__ == '__main__':
    unittest.main()
