import contextlib
import datetime as dt
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/run_prime_relief_cycle.py'
spec = importlib.util.spec_from_file_location('prime_relief_cycle', SCRIPT)
cycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycle)


def fixtures(root):
    (root / 'automation/plans').mkdir(parents=True, exist_ok=True)
    profile = {
        'id': 'a' * 64, 'sessionId': '12345678-1234-1234-1234-123456789abc',
        'jvmStartMs': 1000, 'liveConfigurationSha256': 'b' * 64,
        'rawBounds': {axis: {'min': -1000, 'max': 1000} for axis in cycle.AXES},
    }
    raw = {'X': 20.0, 'Y': 30.0, 'Z': 48.25, 'A': 200.0, 'B': -500.0}
    ledger = {
        'profileId': profile['id'], 'sessionId': profile['sessionId'], 'status': 'verified',
        'entries': [{'id': 'latest', 'status': 'verified', 'plannedGrossDegrees': 10.0}],
        'usedAdditionalGrossDegrees': 10.0, 'pendingRetractDegrees': 0.0,
        'lastVerifiedRaw': dict(raw), 'lastRecordId': 'latest',
    }
    ledger_path = root / 'automation/evidence/operator-paste-runs' / profile['sessionId'] / 'budget-ledger.json'
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger))
    return profile, ledger_path, ledger, raw


class PrimeReliefCycleTests(unittest.TestCase):
    def test_policy_bridge_plans_prime_then_fixed_five_degree_relief(self):
        profile, _, ledger, raw = fixtures(Path(tempfile.mkdtemp()))
        pads = {}
        for i, ref in enumerate(('R1', 'R2')):
            x = 10 + i * 10
            pads[ref] = {
                '1': {'cameraXY': [x, 20], 'tipXY': [x - 1, 20], 'gapAtWorkZ': .5},
                '2': {'cameraXY': [x + 2, 20], 'tipXY': [x + 1, 20], 'gapAtWorkZ': .5},
            }
        profile.update({
            'schema': 1, 'name': 'synthetic', 'safeZ': 32.25, 'travelZ': 53.45,
            'workZ': 58.2, 'gapUncertaintyMm': .3, 'pads': pads,
            'expectedRaw': dict(raw, Z=32.25, B=-10),
            'expectedDriver': dict(raw, Z=32.25, B=-10),
            'expectedNativePoses': {k: {'x': 0, 'y': 0, 'z': 32.25, 'rotation': 0}
                                    for k in ('N1', 'N2', 'top', 'bottom')},
            'rawBounds': {a: {'min': -1000, 'max': 58.2 if a == 'Z' else 1000}
                          for a in cycle.AXES},
            'headClearanceBounds': {h: {k: v for k, v in zip(
                ('minX', 'maxX', 'minY', 'maxY', 'minZ', 'maxZ'),
                (-1000, 1000, -1000, 1000, 0, 100))} for h in ('N1', 'N2')},
            'sourceEvidence': [{'path': '/synthetic', 'sha256': 'c' * 64}],
            'rodBudget': {'baselineGrossDegrees': 1, 'baselineB': -10,
                          'maximumAdditionalGrossDegrees': 100},
        })
        raw.update(Z=32.25, B=-10)
        ledger['lastVerifiedRaw'] = dict(raw)
        plan = cycle.policy_preview(profile, ledger, raw, 10, 5)
        self.assertEqual(plan['prime']['grossDegrees'], 10)
        self.assertEqual(plan['relief']['grossDegrees'], 5)
        self.assertEqual(plan['relief']['endB'], -15)
        too_small = json.loads(json.dumps(profile))
        too_small['rodBudget']['maximumAdditionalGrossDegrees'] = 14
        with self.assertRaises(ValueError):
            cycle.policy_preview(too_small, ledger, raw, 10, 5)

    def test_accepts_fresh_verified_survey_and_z_barrier_format(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile, _, ledger, raw = fixtures(root)
            stamp = dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')
            source = {
                'schema': 1, 'id': 'survey-report',
                'status': 'completed-read-only-position-barrier', 'uncertainCompletion': False,
                'controllerPositionVerified': True, 'liveConfigurationSha256': profile['liveConfigurationSha256'],
                'finishedAt': stamp,
                'request': {'id': 'survey-report', 'jvmStartMs': profile['jvmStartMs'], 'liveConfigurationSha256': profile['liveConfigurationSha256']},
                'afterQuerySnapshot': {'raw': raw, 'driver': raw},
            }
            result = cycle.normalize_source(source, profile, ledger)
            self.assertEqual(result['kind'], 'verified-survey-or-z-report')
            self.assertEqual(result['raw'], raw)

    def test_accepts_only_latest_profile_bound_stationary_native_record(self):
        with tempfile.TemporaryDirectory() as folder:
            profile, _, ledger, raw = fixtures(Path(folder))
            stamp = dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')
            source = {
                'schema': 1,
                'id': 'latest', 'status': 'completed-awaiting-operator-inspection',
                'uncertainCompletion': False, 'noXYZMotion': True, 'stationaryOnly': True,
                'profileId': profile['id'], 'sessionId': profile['sessionId'],
                'liveConfigurationSha256': profile['liveConfigurationSha256'], 'finishedAt': stamp,
                'before': {'raw': {**raw, 'B': raw['B'] + 2}}, 'after': {'raw': raw},
            }
            self.assertEqual(cycle.normalize_source(source, profile, ledger)['kind'], 'latest-stationary-native-record')
            with self.assertRaisesRegex(ValueError, 'latest profile-bound'):
                cycle.normalize_source({**source, 'id': 'older'}, profile, ledger)

    def test_dispatch_failure_is_not_retried_and_relief_is_not_dispatched(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile, ledger_path, ledger, raw = fixtures(root)
            source_path = root / 'source.json'
            stamp = dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')
            source_path.write_text(json.dumps({
                'schema': 1, 'id': 'barrier-report',
                'status': 'completed-read-only-position-barrier', 'uncertainCompletion': False,
                'controllerPositionVerified': True, 'liveConfigurationSha256': profile['liveConfigurationSha256'],
                'finishedAt': stamp,
                'request': {'id': 'barrier-report', 'jvmStartMs': profile['jvmStartMs'], 'liveConfigurationSha256': profile['liveConfigurationSha256']},
                'afterQuerySnapshot': {'raw': raw, 'driver': raw},
            }))
            out_root = root / 'out'
            calls = []

            class CameraProcess:
                def __init__(self): self.terminated = False
                def poll(self): return None
                def terminate(self): self.terminated = True
                def wait(self, timeout=None): return 0
                def kill(self): self.terminated = True

            camera = CameraProcess()
            def dispatch(argv, **kwargs):
                calls.append(argv)
                return subprocess.CompletedProcess(argv, 1, 'dispatch rejected', '')

            def state_loader(_root): return profile, ledger_path, ledger
            with patch.object(cycle, 'verified_initial_capture', return_value={'status': 'complete'}), \
                    patch.object(cycle, 'policy_preview', return_value={'prime': {}, 'relief': {}, 'pendingAfterPrime': 0}), \
                    contextlib.redirect_stdout(io.StringIO()):
                code = cycle.main(['--source', str(source_path), '--execute', '--output-root', str(out_root)],
                                  root=root, dispatch=dispatch, popen=lambda *a, **k: camera,
                                  state_loader=state_loader)
            self.assertEqual(code, 1)
            self.assertEqual(len(calls), 1)
            self.assertIn('operator-prime-segment', calls[0])
            self.assertFalse(any('operator-pressure-relief' in c for c in calls))
            self.assertTrue(camera.terminated)
            self.assertFalse((root / 'automation/plans/operator-prime-segment-request.json').exists())
            result = json.loads(next(out_root.glob('*/result.json')).read_text())
            self.assertEqual(result['status'], 'failed-no-replay')
            self.assertEqual(result['requestedReliefDegrees'], 5)
            self.assertIsNone(result['reliefResult'])

    def test_default_mode_is_preview_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile, ledger_path, ledger, raw = fixtures(root)
            source_path = root / 'source.json'
            stamp = dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')
            source_path.write_text(json.dumps({
                'schema': 1, 'id': 'barrier-report',
                'status': 'completed-read-only-position-barrier', 'uncertainCompletion': False,
                'controllerPositionVerified': True, 'liveConfigurationSha256': profile['liveConfigurationSha256'],
                'finishedAt': stamp,
                'request': {'id': 'barrier-report', 'jvmStartMs': profile['jvmStartMs'], 'liveConfigurationSha256': profile['liveConfigurationSha256']},
                'afterQuerySnapshot': {'raw': raw, 'driver': raw},
            }))
            with patch.object(cycle, 'policy_preview', return_value={'prime': {}, 'relief': {}, 'pendingAfterPrime': 0}), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                code = cycle.main(['--source', str(source_path)], root=root,
                                  state_loader=lambda _root: (profile, ledger_path, ledger))
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(output.getvalue())['previewOnly'])
            self.assertFalse((root / 'automation/plans/operator-prime-segment-request.json').exists())

    def test_stationary_source_accepts_b_only_change_and_scrap_xy_within_purge_envelope(self):
        with tempfile.TemporaryDirectory() as folder:
            profile, _, ledger, _ = fixtures(Path(folder))
            raw = {'X': 355.56, 'Y': 309.76, 'Z': 48.25, 'A': 200.0, 'B': -500.0}
            profile['rawBounds']['X'] = {'min': 0, 'max': 433}
            profile['rawBounds']['Y'] = {'min': 0, 'max': 246.2}
            ledger['lastVerifiedRaw'] = dict(raw)
            stamp = dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')
            source = {
                'schema': 1, 'id': 'latest', 'status': 'completed-awaiting-operator-inspection',
                'uncertainCompletion': False, 'noXYZMotion': True, 'stationaryOnly': True,
                'profileId': profile['id'], 'sessionId': profile['sessionId'],
                'liveConfigurationSha256': profile['liveConfigurationSha256'], 'finishedAt': stamp,
                'before': {'raw': {**raw, 'B': raw['B'] + 2}}, 'after': {'raw': raw},
            }
            result = cycle.normalize_source(source, profile, ledger)
            self.assertEqual(result['raw'], raw)
            outside = {**raw, 'Y': 488}
            ledger['lastVerifiedRaw'] = dict(outside)
            with self.assertRaisesRegex(ValueError, 'stationary purge envelope'):
                cycle.normalize_source({**source, 'before': {'raw': {**outside, 'B': raw['B'] + 2}},
                                        'after': {'raw': outside}}, profile, ledger)


if __name__ == '__main__':
    unittest.main()
