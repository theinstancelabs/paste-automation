import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

from native_fiducial_registration import analyze
from fiducial_registration import fiducials


class NativeFiducialRegistrationTests(unittest.TestCase):
    def fixture(self, root):
        board_path = Path(__file__).resolve().parents[3] / 'pnp/pcb/ftp/ftp.kicad_pcb'
        if not board_path.is_file():
            self.skipTest('canonical FTP CAD is intentionally absent from source-only export')
        raw_fids = fiducials(board_path.read_bytes())
        design = {k: [p[0], -p[1]] for k, p in raw_fids.items()}
        scale, angle, tx, ty = 1.001, .005, 200.0, 100.0
        def mapped(p):
            x, y = p
            return [scale*(math.cos(angle)*x-math.sin(angle)*y)+tx,
                    scale*(math.sin(angle)*x+math.cos(angle)*y)+ty]
        expected = {k: mapped(v) for k, v in design.items()}
        board_fids = [{'reference': k, 'partId': 'FID_PART_'+k,
                       'localXYMm': ([62.4465812,4.69103014] if k=='FID1' else raw_fids[k]), 'savedJobExpectedMachineXYMm': expected[k]}
                      for k in ('FID1', 'FID2', 'FID3')]
        refs = {}
        for i, ref in enumerate(('FID1', 'FID2', 'FID3')):
            folder = root/ref
            folder.mkdir()
            raw_image, native_image = folder/'top-raw.png', folder/'native-pipeline-input.png'
            from PIL import Image, ImageDraw
            image = Image.new('RGB', (240, 300), (5, 5, 5))
            ImageDraw.Draw(image).ellipse((100+i-45, 200+i-45, 100+i+45, 200+i+45), fill=(20, 170, 240))
            # Detector pixels are in captureTransformed/native-pipeline space;
            # captureRaw is 180° oriented on the installed camera.
            image.rotate(180).save(raw_image)
            image.save(native_image)
            before = {k: {'model': v, 'driver': v} for k, v in
                      {'X': expected[ref][0], 'Y': expected[ref][1], 'Z': 32.25, 'A': 720, 'B': -2982}.items()}
            detected = [expected[ref][0]+.01, expected[ref][1]-.01]
            residual = math.dist(detected, expected[ref])
            barrier = {'schema':1,'scope':'position-barrier','status':'completed-read-only-position-barrier','request':{'scope':'read-only-native-position-barrier','id':f'barrier-{i}','jvmStartMs':1,'liveConfigurationSha256':'a'*64},'liveConfigurationSha256':'a'*64,'controllerPositionVerified':True,'uncertainCompletion':False,'noMotionCommandSubmitted':True,'afterQuerySnapshot':{'raw':{k:before[k]['model'] for k in before},'driver':{k:before[k]['driver'] for k in before},'nativePoses':{'top':{'x':expected[ref][0],'y':expected[ref][1],'z':10,'rotation':0}}}}
            barrier_path=folder/'barrier.json';barrier_path.write_text(json.dumps(barrier))
            report = {
                'schema': 1, 'scope': 'native-current-pose-fiducial-vision',
                'status': 'completed-native-fiducial-detection-awaiting-review',
                'requestId': f'12345678-1234-1234-1234-{i:012d}',
                'jvmStartMs': 1, 'liveConfigurationBeforeSha256': 'a'*64,
                'liveConfigurationAfterSha256': 'a'*64, 'jobPath': '/test/ftp.job.xml',
                'sourceBarrier': {'path':str(barrier_path),'sha256':hashlib.sha256(barrier_path.read_bytes()).hexdigest()}, 'sourceBarrierId':f'barrier-{i}', 'sourceBarrierSnapshot':barrier['afterQuerySnapshot'], 'expectedCameraLocationMm':{'x':expected[ref][0],'y':expected[ref][1],'z':10,'rotation':0},
                'board': {'boardId': 'synthetic-board', 'side': 'Top',
                          'localToGlobalMatrix': [1, 0, 0, 1, 0, 0], 'fiducials': board_fids},
                'camera': {'id': 'top-camera', 'locationMm': {'x': expected[ref][0], 'y': expected[ref][1], 'z': 10, 'rotation': 0},
                           'locationAfterMm': {'x': expected[ref][0], 'y': expected[ref][1], 'z': 10, 'rotation': 0},
                           'exposureUsed': 36, 'exposureRestored': True},
                'nativePose': {'cameraLocationMm': {'x': expected[ref][0], 'y': expected[ref][1], 'z': 10, 'rotation': 0}, 'rawAxes': before},
                'modelPoseBefore': before, 'modelPoseAfter': before,
                'images': {'raw': {'path': str(raw_image), 'sha256': hashlib.sha256(raw_image.read_bytes()).hexdigest()},
                           'nativeInput': {'path': str(native_image), 'sha256': hashlib.sha256(native_image.read_bytes()).hexdigest()}},
                'nativeFiducialDetection': {'reference': ref, 'visionSettingsId': 'native-settings',
                    'visionSettingsName': 'Saved fiducial settings', 'expectedMachineXYMm': expected[ref],
                    'detectedMachineXYMm': detected, 'cameraCenterResidualMm': residual,
                    'keypoints': [{'pixel': [100+i, 200+i], 'machineXYMm': detected, 'cameraCenterResidualMm': residual}]},
                'noMotion': True, 'noActuation': True, 'noVacuum': True, 'jobSaved': False,
                'configurationSaved': False, 'modelPoseUnchanged': True, 'configurationRestored': True,
                'physicalRegistrationEstablished': False, 'finishedAt': '2026-10-01T12:00:00Z'
            }
            path = folder/'report.json'
            path.write_text(json.dumps(report))
            refs[ref] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        return {'schema': 1, 'scope': 'native-fiducial-registration-input', 'operator': 'synthetic reviewer',
                'board': str(board_path), 'reports': refs}

    def test_three_native_reports_produce_nonexecution_similarity_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            result = analyze(self.fixture(Path(td)), now_ms=1790856300000)
            self.assertEqual(result['scope'], 'offline-native-fresh-ftp-two-fiducial-transform-with-third-point-check')
            self.assertTrue(result['acceptance']['passed'])
            self.assertLessEqual(result['independentFID3Check']['residualMm'], .08)
            self.assertEqual(len(result['resistorPadMachineXYTargets']), 80)
            self.assertFalse(result['executionReady'])
            self.assertFalse(result['physicalRegistrationEstablished'])

    def test_native_affine_candidate_stays_unaccepted_without_independent_pad_checks(self):
        with tempfile.TemporaryDirectory() as td:
            request = self.fixture(Path(td))
            request['registrationModel'] = 'three-fiducial-affine'
            result = analyze(request, now_ms=1790856300000)
            self.assertEqual(result['scope'], 'offline-native-fresh-ftp-three-fiducial-affine-candidate')
            self.assertFalse(result['acceptance']['passed'])
            self.assertEqual(result['fittedFiducials'], ['FID1', 'FID2', 'FID3'])
            self.assertEqual(result['independentHeldOutPadChecks'], [])
            self.assertEqual(len(result['resistorPadMachineXYTargets']), 80)
            self.assertFalse(result['executionReady'])
            self.assertFalse(result['physicalRegistrationEstablished'])

    def test_requires_distinct_current_same_frame_reports_and_native_image_hashes(self):
        with tempfile.TemporaryDirectory() as td:
            q = self.fixture(Path(td))
            edits = [
                lambda r: r.update(requestId='12345678-1234-1234-1234-000000000000'),
                lambda r: r['modelPoseAfter']['B'].update(model=-2981),
                lambda r: r.update(sourceBarrierId='changed-anchor'),
                lambda r: r['sourceBarrier'].update(sha256='0'*64),
                lambda r: r['nativeFiducialDetection'].update(cameraCenterResidualMm=99),
                lambda r: r['nativeFiducialDetection']['keypoints'][0].update(machineXYMm=[0, 0]),
                lambda r: r['images']['nativeInput'].update(sha256='0'*64),
            ]
            for edit in edits:
                bad = json.loads(json.dumps(q))
                ref = bad['reports']['FID2']['path']
                path = Path(ref); report = json.loads(path.read_text()); edit(report)
                path.write_text(json.dumps(report))
                bad['reports']['FID2']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                with self.subTest(edit=edits.index(edit)), self.assertRaises(ValueError):
                    analyze(bad, now_ms=1790856300000)

    def test_independent_native_fid3_residual_and_fiducial_identity_are_gated(self):
        with tempfile.TemporaryDirectory() as td:
            q = self.fixture(Path(td))
            path = Path(q['reports']['FID3']['path'])
            report = json.loads(path.read_text())
            d = report['nativeFiducialDetection']
            d['detectedMachineXYMm'][0] += .2
            d['keypoints'][0]['machineXYMm'] = d['detectedMachineXYMm']
            d['cameraCenterResidualMm'] = math.dist(d['detectedMachineXYMm'], d['expectedMachineXYMm'])
            path.write_text(json.dumps(report)); q['reports']['FID3']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'FID3'):
                analyze(q, now_ms=1790856300000)
        with tempfile.TemporaryDirectory() as td:
            q = self.fixture(Path(td)); path = Path(q['reports']['FID1']['path'])
            report = json.loads(path.read_text()); report['nativeFiducialDetection']['reference'] = 'FID2'
            path.write_text(json.dumps(report)); q['reports']['FID1']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'another fiducial'):
                analyze(q, now_ms=1790856300000)

    def test_captured_native_report_set_accepts_and_rejects_held_out_fiducial(self):
        evidence = Path(__file__).resolve().parents[2] / 'evidence'
        accepted_ids = {'FID1': 'native-fiducial-static-1790881533981',
                        'FID2': 'native-fiducial-static-1790881613908',
                        'FID3': 'native-fiducial-static-1790881604357'}
        rejected_ids = dict(accepted_ids, FID3='native-fiducial-static-1790881426478')
        if any(not (evidence / folder / 'report.json').is_file()
               for folder in set(accepted_ids.values()) | {rejected_ids['FID3']}):
            self.skipTest('captured native OpenPnP report fixtures are unavailable')

        def request(ids):
            reports = {}
            finish = []
            for ref, folder in ids.items():
                path = evidence / folder / 'report.json'
                raw = path.read_bytes()
                report = json.loads(raw)
                reports[ref] = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}
                finish.append(report['finishedAt'])
            now = max(int(__import__('datetime').datetime.fromisoformat(t.replace('Z', '+00:00')).timestamp() * 1000)
                      for t in finish) + 1
            board_path = Path(__file__).resolve().parents[3] / 'pnp/pcb/ftp/ftp.kicad_pcb'
            return {'request': {'schema': 1, 'scope': 'native-fiducial-registration-input',
                                'operator': 'captured report acceptance test', 'board': str(board_path),
                                'reports': reports}, 'now': now}

        good = request(accepted_ids)
        result = analyze(good['request'], now_ms=good['now'])
        self.assertEqual(result['measurements']['FID1']['designXYMm'], [62.5, 5.0])
        self.assertEqual(result['measurements']['FID2']['designXYMm'], [12.5, 70.0])
        self.assertEqual(result['measurements']['FID3']['designXYMm'], [62.5, 70.0])
        self.assertLessEqual(result['independentFID3Check']['residualMm'], .08)
        bad = request(rejected_ids)
        with self.assertRaisesRegex(ValueError, 'Independent native FID3 check'):
            analyze(bad['request'], now_ms=bad['now'])

    def test_current_static_reports_check_disk_in_native_pipeline_pixel_frame(self):
        evidence = Path(__file__).resolve().parents[2] / 'evidence'
        folders = {'FID1': 'native-fiducial-static-1790924184710',
                   'FID3': 'native-fiducial-static-1790924341712',
                   'FID2': 'native-fiducial-static-1790924462837'}
        if any(not (evidence / folder / 'report.json').is_file() for folder in folders.values()):
            self.skipTest('current static native fiducial reports are unavailable')
        reports = {}
        finished = []
        for ref, folder in folders.items():
            path = evidence / folder / 'report.json'
            raw = path.read_bytes(); report = json.loads(raw)
            reports[ref] = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}
            finished.append(report['finishedAt'])
        now = max(int(__import__('datetime').datetime.fromisoformat(t.replace('Z', '+00:00')).timestamp()*1000)
                  for t in finished) + 1
        board_path = Path(__file__).resolve().parents[3] / 'pnp/pcb/ftp/ftp.kicad_pcb'
        result = analyze({'schema':1,'scope':'native-fiducial-registration-input',
                          'operator':'orientation regression test','board':str(board_path),
                          'reports':reports}, now_ms=now)
        for ref in folders:
            checks = result['measurements'][ref]['coarseBrightDiskChecks']
            self.assertEqual(len(checks), 1)
            self.assertEqual(checks[0]['image'], 'nativeInput')
            self.assertGreaterEqual(checks[0]['occupancy'], .65)


if __name__ == '__main__':
    unittest.main()
