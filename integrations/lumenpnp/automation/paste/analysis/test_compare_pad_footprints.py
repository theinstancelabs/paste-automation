import importlib.util
import tempfile
import unittest
from pathlib import Path
from PIL import Image


SCRIPT = Path(__file__).with_name('compare_pad_footprints.py')
SPEC = importlib.util.spec_from_file_location('compare_pad_footprints', SCRIPT)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class ComparePadFootprintsTests(unittest.TestCase):
    def test_only_new_dark_pixels_inside_reviewed_baseline_pad_are_counted(self):
        with tempfile.TemporaryDirectory() as d:
            before, after = Image.new('L', (20, 20), 30), Image.new('L', (20, 20), 30)
            for y in range(5, 15):
                for x in range(5, 15):
                    before.putpixel((x, y), 230)
                    after.putpixel((x, y), 230)
            for y in range(8, 11):
                for x in range(9, 12):
                    after.putpixel((x, y), 180)
            bp, ap = Path(d) / 'b.png', Path(d) / 'a.png'
            before.save(bp); after.save(ap)
            q = {'schema': 1, 'samePoseReviewed': True,
                 'captureSettings': {'before': {'exposure': 20}, 'after': {'exposure': 20}},
                 'mmPerPixel': {'x': .1, 'y': .2}, 'padRois': [{'padId': 'P1', 'x0': 4, 'y0': 4, 'x1': 16, 'y1': 16}]}
            r = M.compare(bp, ap, q)
        p = r['pads'][0]
        self.assertEqual(p['baselineBrightPadPixelCount'], 100)
        self.assertEqual(p['darkenedPixelCountInsideBaselinePad'], 9)
        self.assertAlmostEqual(p['footprintAreaMm2'], .18)
        self.assertEqual(p['footprintBoundsPx'], {'xMin': 9, 'yMin': 8, 'xMax': 11, 'yMax': 10})
        self.assertFalse(r['manualReviewRequired'])
        self.assertFalse(r['physicalAcceptanceEstablished'])

    def test_capture_mismatch_flags_manual_review_and_missing_pose_review_rejects(self):
        with tempfile.TemporaryDirectory() as d:
            im = Image.new('L', (10, 10), 230)
            bp, ap = Path(d) / 'b.png', Path(d) / 'a.png'
            im.save(bp); im.save(ap)
            q = {'schema': 1, 'samePoseReviewed': True,
                 'captureSettings': {'before': {'exposure': 20}, 'after': {'exposure': 21}},
                 'mmPerPixel': {'x': .1, 'y': .1}, 'padRois': [{'padId': 'P1', 'x0': 1, 'y0': 1, 'x1': 9, 'y1': 9}]}
            self.assertTrue(M.compare(bp, ap, q)['manualReviewRequired'])
            q['samePoseReviewed'] = False
            with self.assertRaisesRegex(ValueError, 'same-pose'):
                M.compare(bp, ap, q)

    def test_explicit_ellipse_excludes_darkened_pixels_outside_copper_mask(self):
        with tempfile.TemporaryDirectory() as d:
            before, after = Image.new('L', (20, 20), 200), Image.new('L', (20, 20), 200)
            after.putpixel((2, 2), 100)  # inside the rectangle, outside the ellipse
            after.putpixel((10, 10), 100)  # inside both
            bp, ap = Path(d) / 'b.png', Path(d) / 'a.png'
            before.save(bp); after.save(ap)
            q = {'schema': 1, 'samePoseReviewed': True,
                 'captureSettings': {'before': {'e': 1}, 'after': {'e': 1}},
                 'mmPerPixel': {'x': .1, 'y': .1}, 'darkeningThreshold': 50,
                 'padBrightnessThreshold': 150,
                 'padRois': [{'padId': 'P1', 'x0': 1, 'y0': 1, 'x1': 19, 'y1': 19,
                             'ellipse': {'cx': 10, 'cy': 10, 'rx': 8, 'ry': 8}}]}
            r = M.compare(bp, ap, q)
        self.assertEqual(r['pads'][0]['darkenedPixelCountInsideBaselinePad'], 1)
        self.assertEqual(r['pads'][0]['footprintBoundsPx'], {'xMin': 10, 'yMin': 10, 'xMax': 10, 'yMax': 10})


if __name__ == '__main__':
    unittest.main()
