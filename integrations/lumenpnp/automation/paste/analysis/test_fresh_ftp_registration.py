import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageDraw

from fresh_ftp_registration import analyze


class FreshFtpRegistrationTests(unittest.TestCase):
    def fixture(self, root, scale=1.001):
        board = Path(__file__).resolve().parents[3] / 'pnp/pcb/ftp/ftp.kicad_pcb'
        if not board.is_file():
            self.skipTest('canonical FTP CAD is intentionally absent from source-only export')
        design = {'FID1': (62.5, 5.0), 'FID2': (12.5, 70.0), 'FID3': (62.5, 70.0)}
        angle, tx, ty = .005, 200.0, 100.0
        def transformed(point):
            x, y = point
            return [scale*(math.cos(angle)*x-math.sin(angle)*y)+tx,
                    scale*(math.sin(angle)*x+math.cos(angle)*y)+ty]
        measurements = {}
        for i, ref in enumerate(('FID1', 'FID2', 'FID3')):
            folder = root/ref
            folder.mkdir()
            image = Image.new('RGB', (64, 64), 'black')
            ImageDraw.Draw(image).ellipse((27, 27, 37, 37), fill=(220, 0, 0))
            image.save(folder/'top.png')
            image_sha = hashlib.sha256((folder/'top.png').read_bytes()).hexdigest()
            xy = transformed(design[ref])
            raw = {'X': xy[0], 'Y': xy[1], 'Z': 26.5, 'A': 200.0, 'B': 720.0}
            poses = {key: {'x': xy[0], 'y': xy[1], 'z': 15.0, 'rotation': 0.0}
                     for key in ('N1', 'N2', 'top', 'bottom')}
            identity = f'12345678-1234-1234-1234-{i:012d}'
            q = {'schema': 2, 'scope': 'camera-survey-single-raw-XY-axis', 'id': identity,
                 'jvmStartMs': 1, 'liveConfigurationSha256': 'a'*64, 'axis': 'X'}
            report = {'schema': 1, 'id': identity, 'status': 'completed-camera-survey-awaiting-image-review',
                      'request': q, 'motionSubmitted': True, 'nativeMotionCompletionReported': True,
                      'controllerPositionVerified': True, 'independentFirmwareStepVerified': True,
                      'uncertainCompletion': False, 'finishedAt': '1970-01-01T00:00:00Z',
                      'after': {'reported': raw},
                      'afterQuerySnapshot': {'raw': raw, 'driver': raw, 'nativePoses': poses},
                      'afterImages': {'top': {'path': 'top.png'}}}
            report_path = folder/'report.json'
            report_bytes = json.dumps(report).encode()
            report_path.write_bytes(report_bytes)
            measurements[ref] = {'report': str(report_path),
                                 'reportSha256': hashlib.sha256(report_bytes).hexdigest(),
                                 'topImageSha256': image_sha,
                                 'fiducialIdentityReviewed': True,
                                 'centeredInTopImageReviewed': True}
        request = {'schema': 1, 'scope': 'fresh-ftp-top-camera-fiducials', 'operator': 'synthetic-review',
                   'board': str(board), 'measurements': measurements,
                   'roi': [10, 10, 54, 54], 'thresholds': [100, 150, 200]}
        return request, transformed

    def test_two_fiducials_and_held_out_third_produce_80_repeatable_xy_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            request, _ = self.fixture(Path(td))
            first = analyze(request, now_ms=1000)
            second = analyze(request, now_ms=1000)
            self.assertEqual(first['resistorPadMachineXYTargets'], second['resistorPadMachineXYTargets'])
            self.assertEqual(len(first['resistorPadMachineXYTargets']), 80)
            self.assertAlmostEqual(first['independentFID3Check']['residualMm'], 0.0)
            self.assertTrue(first['acceptance']['passed'])
            self.assertFalse(first['executionReady'])
            self.assertFalse(first['motionDispatched'])
            self.assertAlmostEqual(first['transformFromFID1FID2']['scale'], 1.001)

    def test_unreviewed_identity_hash_or_centered_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            request, _ = self.fixture(Path(td))
            for field, value in [('fiducialIdentityReviewed', False),
                                 ('centeredInTopImageReviewed', False),
                                 ('reportSha256', '0'*64)]:
                bad = json.loads(json.dumps(request))
                bad['measurements']['FID1'][field] = value
                with self.assertRaises(ValueError):
                    analyze(bad, now_ms=1000)
            offcenter = Path(td)/'offcenter'
            offcenter.mkdir()
            bad, _ = self.fixture(offcenter)
            image_path = Path(bad['measurements']['FID2']['report']).parent/'top.png'
            image = Image.new('RGB', (64, 64), 'black')
            ImageDraw.Draw(image).ellipse((37, 27, 47, 37), fill=(220, 0, 0))
            image.save(image_path)
            bad['measurements']['FID2']['topImageSha256'] = hashlib.sha256(image_path.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                analyze(bad, now_ms=1000)

    def test_third_point_or_session_change_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            request, transform = self.fixture(Path(td))
            report_path = Path(request['measurements']['FID3']['report'])
            report = json.loads(report_path.read_text())
            for key in ('raw', 'driver'):
                report['afterQuerySnapshot'][key]['X'] += .2
            for key in ('N1', 'N2', 'top', 'bottom'):
                report['afterQuerySnapshot']['nativePoses'][key]['x'] += .2
            report['after']['reported']['X'] += .2
            # Also move the measured image is not sufficient; counts/position must remain report-bound.
            changed = json.dumps(report).encode()
            report_path.write_bytes(changed)
            request['measurements']['FID3']['reportSha256'] = hashlib.sha256(changed).hexdigest()
            with self.assertRaises(ValueError):
                analyze(request, now_ms=1000)

        with tempfile.TemporaryDirectory() as td:
            request, _ = self.fixture(Path(td))
            report_path = Path(request['measurements']['FID2']['report'])
            report = json.loads(report_path.read_text())
            report['request']['liveConfigurationSha256'] = 'b'*64
            changed = json.dumps(report).encode()
            report_path.write_bytes(changed)
            request['measurements']['FID2']['reportSha256'] = hashlib.sha256(changed).hexdigest()
            with self.assertRaises(ValueError):
                analyze(request, now_ms=1000)

    def test_stale_input_and_unreasonable_scale_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            request, _ = self.fixture(Path(td))
            with self.assertRaisesRegex(ValueError, '30 minutes'):
                analyze(request, now_ms=31*60*1000)
        with tempfile.TemporaryDirectory() as td:
            request, _ = self.fixture(Path(td), scale=1.02)
            with self.assertRaisesRegex(ValueError, 'scale'):
                analyze(request, now_ms=1000)


if __name__ == '__main__':
    unittest.main()
