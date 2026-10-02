import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name('prepare-startup-quarantine-request.py')
SPEC = importlib.util.spec_from_file_location('prepare_startup_quarantine_request', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def report(**changes):
    value = {
        'scope': 'pure-model-state-no-controller-access',
        'time': '2026-10-01T20:24:07.707Z',
        'jvmStartMs': 1790886238424,
        'enabled': False,
        'homed': False,
        'busy': False,
        'liveConfigurationSha256': 'a' * 64,
        'drivers': [{'connected': False, 'motionPending': False}],
        'nozzles': [{'name': 'N2', 'tip': None, 'compatible': 0,
                     'changer': False, 'part': None}],
    }
    value.update(changes)
    return value


class PrepareStartupQuarantineRequestTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'report.json'

    def make(self, value):
        self.path.write_text(json.dumps(value))
        return MODULE.prepare(self.path, 'Root operator',
                              'Reviewed current startup state and authorize only the N2 exclusion unset.',
                              now_ms=1790886300000, request_id='b62bec34-6c6b-4dfd-8b2e-006ad312ce10')

    def test_binds_exact_fresh_source_and_allows_disabled_or_enabled_unhomed_startup(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                self.path.unlink(missing_ok=True)
                q = self.make(report(enabled=enabled))
                self.assertEqual(q['expectedEnabled'], enabled)
                self.assertEqual(q['expectedLiveConfigurationSha256'], 'a' * 64)
                self.assertEqual(q['sourceEvidence']['sha256'], MODULE.evidence(self.path)['sha256'])
                self.assertEqual(q['action'], 'unset-manual-nozzle-tip-change-location-only')

    def test_rejects_stale_or_unsafe_source_states(self):
        mutations = [
            {'scope': 'other'}, {'homed': True}, {'busy': True},
            {'drivers': [{'connected': True, 'motionPending': False}]},
            {'drivers': [{'connected': False, 'motionPending': True}]},
            {'nozzles': [{'name': 'N2', 'tip': 'NT2', 'compatible': 1,
                          'changer': False, 'part': None}]},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.path.unlink(missing_ok=True)
                with self.assertRaises(ValueError):
                    self.make(report(**mutation))

    def test_requires_review_basis(self):
        self.path.write_text(json.dumps(report()))
        with self.assertRaises(ValueError):
            MODULE.prepare(self.path, 'Root', 'too short', now_ms=1790886300000)

    def test_explicit_homed_connected_variant_binds_idle_reader_and_current_manual_location(self):
        value = report(
            enabled=True, homed=True,
            drivers=[{'connected': True, 'readerAlive': True, 'error': None,
                      'motionPending': False}],
            taskOwner=None, motionQueue=0, preRotate=False,
            executor={'shutdown': False, 'terminated': False, 'active': 0, 'queued': 0},
            nozzles=[{'name': 'N2', 'tip': None, 'compatible': 0,
                      'changer': False, 'part': None,
                      'manualNozzleTipChangeLocation': {
                          'initialized': True, 'location': 'X:1.0 Y:2.0 Z:3.0 R:0.0'}}])
        self.path.write_text(json.dumps(value))
        q = MODULE.prepare(self.path, 'Root operator',
                           'Reviewed current connected homed idle state; unset only the N2 manual exclusion location.',
                           now_ms=1790886300000, request_id='b62bec34-6c6b-4dfd-8b2e-006ad312ce10',
                           restore_variant=MODULE.HOMED)
        self.assertTrue(q['expectedHomed'])
        self.assertTrue(q['expectedDriverConnected'])
        self.assertEqual(q['expectedManualLocation'], 'X:1.0 Y:2.0 Z:3.0 R:0.0')
        self.assertEqual(q['restoreVariant'], MODULE.HOMED)

    def test_homed_variant_rejects_any_live_work_or_fault(self):
        base = report(
            enabled=True, homed=True,
            drivers=[{'connected': True, 'readerAlive': True, 'error': None,
                      'motionPending': False}],
            taskOwner=None, motionQueue=0, preRotate=False,
            executor={'shutdown': False, 'terminated': False, 'active': 0, 'queued': 0},
            nozzles=[{'name': 'N2', 'tip': None, 'compatible': 0,
                      'changer': False, 'part': None,
                      'manualNozzleTipChangeLocation': {'initialized': True, 'location': 'old'}}])
        mutations = [
            {'drivers': [{'connected': True, 'readerAlive': False, 'error': None, 'motionPending': False}]},
            {'drivers': [{'connected': True, 'readerAlive': True, 'error': 'fault', 'motionPending': False}]},
            {'drivers': [{'connected': True, 'readerAlive': True, 'error': None, 'motionPending': True}]},
            {'motionQueue': 1}, {'executor': {'shutdown': False, 'terminated': False, 'active': 1, 'queued': 0}},
            {'executor': {'shutdown': False, 'terminated': False, 'active': 0, 'queued': 1}},
            {'preRotate': True}, {'taskOwner': {'name': 'worker'}},
            {'nozzles': [{'name': 'N2', 'tip': None, 'compatible': 0, 'changer': False,
                          'part': None, 'manualNozzleTipChangeLocation': {'initialized': False, 'location': None}}]},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.path.unlink(missing_ok=True)
                candidate = dict(base)
                candidate.update(mutation)
                self.path.write_text(json.dumps(candidate))
                with self.assertRaises(ValueError):
                    MODULE.prepare(self.path, 'Root operator',
                                   'Reviewed current connected homed idle state; unset only the N2 manual exclusion location.',
                                   now_ms=1790886300000, restore_variant=MODULE.HOMED)


if __name__ == '__main__':
    unittest.main()
