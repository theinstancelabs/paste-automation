import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageDraw

from fresh_ftp_registration import analyze, affine_from_three


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

    def affine_fixture(self, root):
        request, _ = self.fixture(root)
        request['registrationModel'] = 'three-fiducial-affine'
        candidate = analyze(request, now_ms=1000)
        targets = {p['padId']: p['machineXYMm'] for p in candidate['resistorPadMachineXYTargets']}
        template = json.loads(Path(request['measurements']['FID1']['report']).read_text())
        def proof(name, xy):
            folder = root/name; folder.mkdir()
            Image.new('RGB', (256, 256), 'white').save(folder/'top.png')
            r = json.loads(json.dumps(template)); r['id'] = r['request']['id'] = name
            for key in ('raw', 'driver'):
                r['afterQuerySnapshot'][key].update(X=xy[0], Y=xy[1])
            r['after']['reported'].update(X=xy[0], Y=xy[1])
            for pose in r['afterQuerySnapshot']['nativePoses'].values():
                pose.update(x=xy[0], y=xy[1])
            path = folder/'report.json'; path.write_text(json.dumps(r))
            ev = lambda p: dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            return ev(path), ev(folder/'top.png')
        samples = []
        for i, (xy, center) in enumerate([([0,0],[127.5,127.5]),([1,0],[227.5,127.5]),([1,1],[227.5,27.5])]):
            report, image = proof('J'+str(i), xy)
            samples.append(dict(report=report, image=image, rawXY=xy, centerPixels=center))
        j = dict(schema=1, scope='measured-top-camera-image-jacobian',
                 session={k:candidate['session'][k] for k in ('jvmStartMs','liveConfigurationSha256')},
                 fixedRawZAB=candidate['session']['fixedRawZAB'], reviewedBy='test', reviewedMs=900,
                 pixelShiftPerCameraMm=[[100,0],[0,-100]], sourceMeasurements=samples)
        path=root/'jacobian.json'; path.write_text(json.dumps(j))
        request['imageJacobianEvidence']=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        request['heldOutPadChecks']=[]
        for pad in ('R1.2','R16.1','R40.1'):
            report,image=proof(pad,targets[pad])
            request['heldOutPadChecks'].append(dict(padId=pad,report=report['path'],reportSha256=report['sha256'],
                topImageSha256=image['sha256'],padIdentityReviewed=True,centerMeasurementReviewed=True,observedCenterPixel=[127.5,127.5]))
        return request

    def fast_camera_fixture(self, root):
        request, _ = self.fixture(root)
        for i, ref in enumerate(('FID1', 'FID2', 'FID3')):
            item=request['measurements'][ref];path=Path(item['report']);report=json.loads(path.read_text());q=report['request']
            raw=report['afterQuerySnapshot']['raw'];raw['X']=round(raw['X'],2);raw['Y']=round(raw['Y'],2)
            driver=report['afterQuerySnapshot']['driver'];driver.update(X=raw['X'],Y=raw['Y'])
            poses=report['afterQuerySnapshot']['nativePoses']
            for pose in poses.values():pose.update(x=raw['X'],y=raw['Y'])
            start=dict(raw);start['X']-=.1;start_poses=json.loads(json.dumps(poses))
            for name,pose in start_poses.items():
                if name!='bottom':pose['x']-=.1
            report['after']['reported'].update(X=raw['X'],Y=raw['Y'])
            fid_q={'schema':1,'scope':'camera-only-registered-fast-inspection','enabled':True,'id':q['id'],'jvmStartMs':1,
              'liveConfigurationSha256':'a'*64,'mode':'registered-fiducials','references':[ref],
              'targets':[{'reference':ref,'x':raw['X'],'y':raw['Y'],'pads':[]}], 'operatorReviewed':True,'reviewedBy':'test',
              'speedFraction':1,'speedOverPrecision':True,'maxSegmentMm':10,'maxTotalTravelMm':120,'plannedDistanceMm':.1,
              'completionScope':'Camera frames and XY position reports only; no paste, calibration, or placement acceptance.',
              'expectedRaw':start,'expectedDriver':start,'expectedNativePoses':start_poses,
              'routeSteps':[{'index':0,'x':raw['X'],'y':raw['Y'],'z':raw['Z'],'a':raw['A'],'b':raw['B'],'captureReferences':[ref]}]}
            report.update(scope='camera-only-registered-fast-inspection',request=fid_q,motionSubmitted=True,
                          nativeMotionCompletionReported=True,physicalAcceptanceEstablished=False,calibrationEstablished=False,
                          beforeQuerySnapshot={'raw':start,'driver':start,'nativePoses':start_poses},beforeReported=start,
                          afterReported=raw,transitions=[{'status':'route-step-0-verified'}],
                          frames=[{'reference':ref,'path':'top.png','width':64,'height':64,'rawAxes':raw,'nativePose':poses['top']}])
            report_bytes=json.dumps(report).encode();path.write_bytes(report_bytes)
            item['reportSha256']=hashlib.sha256(report_bytes).hexdigest()
        return request

    def test_fast_camera_report_family_is_bound_without_relabeling(self):
        with tempfile.TemporaryDirectory() as td:
            request=self.fast_camera_fixture(Path(td));result=analyze(request,now_ms=1000)
            self.assertTrue(result['acceptance']['passed'])
            self.assertEqual(len(result['resistorPadMachineXYTargets']),80)
            self.assertTrue(all(m['report']['path'].endswith('report.json') for m in result['measurements'].values()))
            for edit in (lambda r:r['request'].update(scope='camera-survey-single-raw-XY-axis'),
                         lambda r:r['afterQuerySnapshot']['driver'].update(B=42),
                         lambda r:r['afterReported'].update(X=-1),
                         lambda r:r['request']['routeSteps'][0].update(b=43),
                         lambda r:r['frames'][0].update(reference='FID2')):
                bad=json.loads(json.dumps(request));ref='FID1';p=Path(bad['measurements'][ref]['report']);report=json.loads(p.read_text());edit(report);changed=json.dumps(report).encode();p.write_bytes(changed);bad['measurements'][ref]['reportSha256']=hashlib.sha256(changed).hexdigest()
                with self.assertRaises(ValueError):analyze(bad,now_ms=1000)

    def test_affine_candidate_requires_three_independent_held_out_pads(self):
        with tempfile.TemporaryDirectory() as td:
            q=self.affine_fixture(Path(td)); accepted=analyze(q,now_ms=1000)
            self.assertTrue(accepted['acceptance']['passed'])
            self.assertNotIn('independentFID3Check',accepted)
            self.assertEqual(len(accepted['independentHeldOutPadChecks']),3)
            self.assertFalse(accepted['executionReady'])
            del q['heldOutPadChecks']
            self.assertFalse(analyze(q,now_ms=1000)['acceptance']['passed'])

    def test_affine_rejects_wrong_jacobian_and_bad_heldout(self):
        with tempfile.TemporaryDirectory() as td:
            q=self.affine_fixture(Path(td))
            for edit in (lambda x:x['heldOutPadChecks'][0].update(observedCenterPixel=[136,127.5]),
                         lambda x:x['heldOutPadChecks'][0].update(centerMeasurementReviewed=False),
                         lambda x:x['heldOutPadChecks'].pop(),
                         lambda x:x['imageJacobianEvidence'].update(sha256='0'*64)):
                bad=json.loads(json.dumps(q));edit(bad)
                with self.assertRaises(ValueError):analyze(bad,now_ms=1000)
            path=Path(q['imageJacobianEvidence']['path']);j=json.loads(path.read_text())
            j['pixelShiftPerCameraMm'][0][0]=99;path.write_text(json.dumps(j))
            q['imageJacobianEvidence']['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'displacements'):analyze(q,now_ms=1000)

    def test_affine_orientation_scale_and_skew_are_bounded(self):
        design=[[0,0],[1,0],[0,1]]
        affine_from_three(design,[[0,0],[1.001,0],[.002,.999]])
        for points in ([[0,0],[-1,0],[0,1]], [[0,0],[1.02,0],[0,1]], [[0,0],[1,0],[.008,1]]):
            with self.assertRaises(ValueError):affine_from_three(design,points)

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
