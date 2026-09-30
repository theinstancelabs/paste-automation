import math
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import deposit_metrics
from deposit_metrics import measure, analyze, source, load_mask


def rectangle(x0, y0, x1, y1, width=20):
    return {y*width+x for x in range(x0, x1) for y in range(y0, y1)}


class DepositMetricsTests(unittest.TestCase):
    def test_empty_deposit_is_zero_not_acceptance(self):
        r = measure((20, 20), {'R1.1': rectangle(2, 2, 6, 6)}, set(), .01, .02)
        self.assertEqual(r['pads'][0]['coverageFraction'], 0)
        self.assertIsNone(r['pads'][0]['coveredCentroidOffsetMm'])
        self.assertFalse(r['physicalAcceptanceEstablished'])
        self.assertIsNone(r['pasteVolumeMm3'])

    def test_anisotropic_area_and_signed_centroid(self):
        r = measure((20, 20), {'p': rectangle(2, 2, 6, 6)}, rectangle(4, 2, 6, 6), .01, .02)
        p = r['pads'][0]
        self.assertEqual(p['coverageFraction'], .5)
        self.assertAlmostEqual(p['coveredAreaMm2'], .0016)
        self.assertAlmostEqual(p['coveredCentroidOffsetMm']['x'], .01)
        self.assertAlmostEqual(p['coveredCentroidOffsetMm']['y'], 0)

    def test_bridge_spill_is_not_silently_assigned_to_one_pad(self):
        pads = {'a': rectangle(2, 2, 5, 5), 'b': rectangle(7, 2, 10, 5)}
        paste = rectangle(2, 3, 10, 4)
        r = measure((20, 20), pads, paste, .1, .1)
        self.assertEqual(r['bridgeCandidates'][0]['padIds'], ['a', 'b'])
        self.assertTrue(all(p['sharedComponent'] for p in r['pads']))
        self.assertAlmostEqual(r['spillOutsideAllPadsMm2'], .02)

    def test_diagonal_connections_and_row_wrapping(self):
        r = measure((20, 20), {'p': {19}}, {19, 20, 41}, .1, .1)
        self.assertEqual(r['depositComponentCount'], 2)
        self.assertTrue(r['depositTouchesImageEdge'])

    def test_reject_overlap_empty_and_bad_scale(self):
        for masks in ({'a': {10}, 'b': {10}}, {'a': set()}, {}):
            with self.assertRaises(ValueError):
                measure((20, 20), masks, set(), .1, .1)
        for scale in (0, -1, float('nan'), float('inf'), True):
            with self.assertRaises(ValueError):
                measure((20, 20), {'a': {10}}, set(), scale, .1)

    def test_disconnected_spill_and_tail_count(self):
        r = measure((20, 20), {'p': rectangle(5, 5, 8, 8)}, {105, 106, 107, 108, 250}, .1, .1)
        p = r['pads'][0]
        self.assertEqual(r['depositComponentCount'], 2)
        self.assertEqual(p['touchingComponentCount'], 1)
        self.assertAlmostEqual(p['touchingDepositSpillOutsideAllPadsMm2'], .01)
        self.assertAlmostEqual(r['spillOutsideAllPadsMm2'], .02)

    def test_dimensions_and_image_coordinate_labels(self):
        for size in ((0, 20), (20, -1), (True, 20), (20.0, 20), (20,), '20'):
            with self.assertRaises(ValueError):
                measure(size, {'p': {0}}, set(), .1, .1)
        r = measure((2, 2), {'p': {0, 2}}, {2}, .1, .2)
        self.assertAlmostEqual(r['pads'][0]['coveredCentroidOffsetMm']['y'], .1)
        self.assertIn('Y down', r['coordinateFrame'])
        self.assertEqual(r['componentConnectivity'], 8)

    def test_mask_digest_uses_exact_decoded_bytes_even_if_file_changes(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'mask.png'
            Image.new('L', (2, 2), 255).save(path)
            original = path.read_bytes()
            decode = deposit_metrics.binary_mask_bytes

            def replace_after_decode(data):
                result = decode(data)
                Image.new('L', (2, 2), 0).save(path)
                return result

            with patch.object(deposit_metrics, 'binary_mask_bytes', side_effect=replace_after_decode):
                size, pixels, reference = load_mask(path)
            self.assertEqual(pixels, {0, 1, 2, 3})
            self.assertEqual(reference['sha256'], hashlib.sha256(original).hexdigest())
            self.assertNotEqual(reference, source(path))

    def test_analyze_hashes_masks_and_checks_original_image_reference(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'mask.png'
            Image.new('L', (2, 2), 255).save(path)
            q = {'schema': 1, 'masksReviewedAndAligned': True, 'reviewer': 'synthetic',
                 'segmentationMethod': 'synthetic', 'registrationRecord': 'synthetic',
                 'scaleRecord': 'synthetic', 'sourceImages': [source(path)],
                 'pasteMask': str(path), 'pads': [{'id': 'p', 'mask': str(path)}],
                 'mmPerPixelX': .1, 'mmPerPixelY': .2}
            r = analyze(q)
            self.assertEqual(r['maskReferences']['paste'], source(path))
            self.assertEqual(r['pads'][0]['coverageFraction'], 1)
            q['sourceImages'][0]['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                analyze(q)

    def test_masks_reject_non_png_nonbinary_or_non_grayscale(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'mask.png'
            for image, fmt in ((Image.new('L', (2, 2), 255), 'TIFF'),
                               (Image.new('L', (2, 2), 128), 'PNG'),
                               (Image.new('RGB', (2, 2), 'white'), 'PNG')):
                image.save(path, format=fmt)
                with self.assertRaises(ValueError):
                    load_mask(path)


if __name__ == '__main__':
    unittest.main()
