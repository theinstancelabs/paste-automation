import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'paste/prepare-survey-request.py'
spec = importlib.util.spec_from_file_location('prepare_survey_request', MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW = 1790000000000
SOURCE_ID = '12345678-1234-1234-1234-123456789abc'


def report(audit=False):
    raw = {'X': 30.1234, 'Y': 40.125, 'Z': 20, 'A': 50, 'B': 720}
    firmware = {**raw, 'X': 30.12, 'Y': 40.13}
    poses = {name: {'x': 1, 'y': 2, 'z': 3, 'rotation': 4} for name in ('N1', 'N2', 'top', 'bottom')}
    r = {'schema': 1, 'afterQuerySnapshot': {'raw': raw, 'driver': raw, 'nativePoses': poses}}
    identity = {'jvmStartMs': NOW-1000000, 'liveConfigurationSha256': 'a'*64}
    if audit:
        r.update(scope='read-only-specific-survey-stop-audit', status=module.AUDIT_SUCCESS,
                 faultId=SOURCE_ID, faultSha256='b'*64, positionVerified=True, stationaryImagesCaptured=True, motionIssued=False,
                 latchCleared=False, reported=firmware, **identity)
    else:
        r.update(id=SOURCE_ID, request={'id': SOURCE_ID, 'scope': module.SCOPE,
                 'expectedRaw': {**raw, 'X': 20.1234}, **identity}, status=module.SUCCESS,
                 motionSubmitted=True, nativeMotionCompletionReported=True, controllerPositionVerified=True,
                 independentFirmwareStepVerified=True, uncertainCompletion=False, after={'reported': firmware})
    return r


class PrepareSurveyRequestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'report.json'
        self.image = self.root/'corridor.png'
        self.image.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic-test-only')
        os.utime(self.image, ns=((NOW-1000)*1000000, (NOW-1000)*1000000))

    def prepare(self, data=None, reviewed=True):
        self.source.write_text(json.dumps(report() if data is None else data))
        return module.prepare(self.source, self.image, 'test operator', reviewed, NOW)

    def test_uses_terminal_pose_and_latest_reported_driver_not_old_start(self):
        q, info = self.prepare()
        self.assertEqual(q['expectedRaw']['X'], 30.1234)
        self.assertEqual(q['expectedDriver']['X'], 30.12)
        self.assertEqual(q['corridorEvidence']['capturedMs'], NOW-1000)
        self.assertFalse(info['dispatchPerformed'])
        self.assertEqual(q['axis'], 'X')
        self.assertEqual(q['deltaMm'], 10)
        self.assertNotEqual(q['id'], SOURCE_ID)
        other, _ = self.prepare()
        self.assertNotEqual(q['id'], other['id'])

    def test_only_completed_stationary_narrow_audit_is_accepted(self):
        q, info = self.prepare(report(True))
        self.assertTrue(info['separateLatchReleaseRequiredForAuditSource'])
        self.assertEqual(q['expectedDriver']['Y'], 40.13)
        for key in ('positionVerified', 'stationaryImagesCaptured'):
            r = report(True);r[key] = False
            with self.assertRaises(ValueError): self.prepare(r)

    def test_failed_uncertain_and_unverified_sources_never_generate_replay(self):
        for patch in ({'status': 'failed-no-retry-no-recovery-motion'}, {'uncertainCompletion': True},
                      {'controllerPositionVerified': False}, {'independentFirmwareStepVerified': False},
                      {'schema': True}, {'error': 'fault'}, {'auditIncomplete': True}):
            r = report();r.update(patch)
            with self.assertRaises(ValueError): self.prepare(r)

    def test_no_missing_or_guessed_coords_and_no_foreign_snapshot(self):
        r = report();del r['afterQuerySnapshot']['raw']['B']
        with self.assertRaises(ValueError): self.prepare(r)
        r = report();r['after']['reported']['Z'] = 21
        with self.assertRaises(ValueError): self.prepare(r)
        r = report();r['afterQuerySnapshot']['nativePoses']['N2']['z'] = None
        with self.assertRaises(ValueError): self.prepare(r)

    def test_stale_future_or_nonimage_evidence_and_unreviewed_flag_rejected(self):
        with self.assertRaises(ValueError): self.prepare(reviewed=False)
        for stamp in (NOW-300001, NOW+1):
            os.utime(self.image, ns=(stamp*1000000, stamp*1000000))
            with self.assertRaises(ValueError): self.prepare()
        os.utime(self.image, ns=(NOW*1000000, NOW*1000000))
        self.image.write_bytes(b'not an image')
        os.utime(self.image, ns=(NOW*1000000, NOW*1000000))
        with self.assertRaises(ValueError): self.prepare()

    def test_explicit_signed_xy_step_and_legacy_source(self):
        old = report();old['request']['scope'] = module.LEGACY_SCOPE
        self.source.write_text(json.dumps(old))
        for axis in ('X', 'Y'):
            for delta in (-10, -0.5, 0.5, 10):
                q, _ = module.prepare(self.source, self.image, 'operator', True, NOW, axis, delta)
                self.assertEqual((q['schema'], q['axis'], q['deltaMm']), (2, axis, delta))
                self.assertNotIn('deltaRawXmm', q)
        for axis, delta in [('Z', 1), ('XY', 1), ('Y', 0), ('Y', 10.01), ('Y', -10.01), ('Y', float('nan')), ('X', True)]:
            with self.assertRaises(ValueError):
                module.prepare(self.source, self.image, 'operator', True, NOW, axis, delta)

    def test_completed_signed_z_and_read_only_barrier_sources(self):
        r = report();r['status']='completed-Z-observation-awaiting-image-review';r['request']['scope']='bounded-signed-raw-Z-observation'
        q, _ = self.prepare(r);self.assertEqual(q['expectedRaw']['B'],720)
        r['request']['scope']='single-bounded-raw-Z-observation'
        with self.assertRaises(ValueError):self.prepare(r)
        r = report();r.update(status='completed-read-only-position-barrier',noMotionCommandSubmitted=True,reported=r['after']['reported'],liveConfigurationSha256='a'*64);r['request']['scope']='read-only-native-position-barrier'
        q, _ = self.prepare(r);self.assertEqual(q['expectedDriver']['X'],30.12)
        r['request']['id']='00000000-0000-0000-0000-000000000000'
        with self.assertRaises(ValueError):self.prepare(r)

    def test_output_refuses_overwrite_and_exact_template_field_set(self):
        q, _ = self.prepare()
        self.assertEqual(set(q), set(json.loads(MODULE.with_name('survey-request.pending.json').read_text())))
        out = self.root/'request.json'
        module.write_request(out, q)
        first = out.read_bytes()
        with self.assertRaises(FileExistsError): module.write_request(out, q)
        self.assertEqual(out.read_bytes(), first)


if __name__ == '__main__':
    unittest.main()
