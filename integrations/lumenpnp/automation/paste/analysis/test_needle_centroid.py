import io
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from needle_centroid import sweep, analyze_reports, fit_current_plane


def image_bytes():
    image = Image.new('RGB', (20, 20))
    for x in range(8, 11):
        for y in range(9, 12):
            image.putpixel((x, y), (0, 200, 0))
    data = io.BytesIO()
    image.save(data, format='PNG')
    return data.getvalue()


class NeedleCentroidTests(unittest.TestCase):
    def test_known_local_jacobian_and_repeat_returns_not_physical_calibration(self):
        frames = []
        for x, y in [(0, 0), (1, 0), (0, 1), (0, 0)]:
            frames.append({'reportedRaw': {'X': x, 'Y': y}, 'measurement': {
                'geometricImageCenterPixelIndex': {'x': 50, 'y': 50},
                'centroidSummary': {'x': {'median': 50+10*x+y}, 'y': {'median': 50-2*x+12*y}},
                'thresholds': [{'selected': {'touchesRoiEdge': False, 'equalAreaAmbiguity': False}}]}})
        result = fit_current_plane({'frames': frames})
        for actual, expected in zip(result['pixelRowsRawXYColumns'], [[10, 1], [-2, 12]]):
            for a, e in zip(actual, expected):
                self.assertAlmostEqual(a, e)
        self.assertAlmostEqual(result['rmsRadialResidualPixels'], 0)
        self.assertAlmostEqual(result['estimatedRawAtGeometricImageCenter']['X'], 0)
        self.assertFalse(result['physicalCalibrationEstablished'])
        self.assertEqual(result['repeatReturns'][0]['count'], 2)
        with self.assertRaises(ValueError):
            fit_current_plane({'frames': frames[:2]})
        frames[0]['measurement']['thresholds'][0]['selected']['touchesRoiEdge'] = True
        with self.assertRaises(ValueError):
            fit_current_plane({'frames': frames})

    def test_known_feature_centroid_frame_and_no_invented_calibration(self):
        result = sweep(image_bytes(), (5, 5, 15, 15), [100, 180, 220])
        self.assertEqual(result['centroidSummary']['x']['median'], 9)
        self.assertEqual(result['centroidSummary']['y']['median'], 10)
        self.assertIsNone(result['thresholds'][-1]['selected'])
        self.assertEqual(result['geometricImageCenterPixelIndex'], {'x': 9.5, 'y': 9.5})
        self.assertFalse(result['featureIdentityConfirmed'])
        self.assertFalse(result['physicalCalibrationEstablished'])

    def test_edge_and_threshold_validation(self):
        result = sweep(image_bytes(), (8, 9, 11, 12), [100])
        self.assertTrue(result['thresholds'][0]['selected']['touchesRoiEdge'])
        for roi, thresholds in [((0, 0, 21, 20), [100]), ((0, 0, 0, 20), [100]),
                                ((0, 0, 20, 20), [100, 100]), ((0, 0, 20, 20), [256])]:
            with self.assertRaises(ValueError):
                sweep(image_bytes(), roi, thresholds)

    def test_hashes_original_bytes_and_rejects_z_change_or_unverified_run(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for i in range(2):
                directory = Path(folder) / str(i)
                directory.mkdir()
                (directory / 'bottom.png').write_bytes(image_bytes())
                report = {'status': 'completed-camera-survey-awaiting-image-review',
                          'controllerPositionVerified': True, 'independentFirmwareStepVerified': True,
                          'uncertainCompletion': False, 'after': {'reported': {'X': i, 'Y': 2, 'Z': 26.5, 'A': 200, 'B': 720}},
                          'request': {'jvmStartMs': 1, 'liveConfigurationSha256': 'a'*64},
                          'afterImages': {'bottom': {'path': 'bottom.png'}}}
                path = directory / 'report.json'
                path.write_text(json.dumps(report))
                paths.append(path)
            result = analyze_reports(paths, (5, 5, 15, 15), [100])
            self.assertEqual(result['fixedRawAxes'], {'Z': 26.5, 'A': 200, 'B': 720})
            self.assertEqual(len(result['frames'][0]['imageReference']['sha256']), 64)
            report['after']['reported']['Z'] = 26.4
            paths[-1].write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'Z/A/B changed'):
                analyze_reports(paths, (5, 5, 15, 15), [100])
            report['controllerPositionVerified'] = False
            paths[-1].write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'verified completed'):
                analyze_reports(paths, (5, 5, 15, 15), [100])


if __name__ == '__main__':
    unittest.main()
