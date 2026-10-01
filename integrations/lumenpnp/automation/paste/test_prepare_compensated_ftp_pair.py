import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('prepare-compensated-ftp-pair.py')
SPEC = importlib.util.spec_from_file_location('prepare_compensated_ftp_pair', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CompensatedPairBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ev_path = self.root / 'evidence.json'
        self.ev_path.write_text('{"authored":true}\n')
        self.ev = MODULE.evidence(self.ev_path)
        self.reg_path = self.root / 'registration.json'
        self.raw = {'X': 0.0, 'Y': 0.0, 'Z': 53.4, 'A': 720.0, 'B': -1000.0}
        self.poses = {'N1': {'x': 0, 'y': 0, 'z': 53.4}, 'N2': {'x': 0, 'y': 0, 'z': 53.4}}
        self.target = {
            'schema': 1, 'scope': 'ftp-two-pad-commissioning-targets',
            'surface': {'rawZ': 58.3, 'estimatedGapMm': 0.4, 'gapUncertaintyMm': 0.3},
            'cameraMinusTipXYMm': [0, 0],
            'compensatedSequence': {
                'schema': 1, 'protocol': 'restore-dose-retract-lift-two-pad',
                'doseDegrees': 4, 'retractDegrees': 2, 'dwellMilliseconds': 300,
                'retractDwellMilliseconds': 500, 'idleReliefDegrees': 40,
                'conditioningFinishedMs': 12345, 'conditioningReportEvidence': self.ev,
                'conditioningLedgerEvidence': self.ev, 'preparationExperimentEvidence': self.ev,
                'tipObservationEvidence': self.ev, 'authoredObservation': {'capturedMs': 12300},
            },
            'cadEvidence': self.ev, 'registrationEvidence': MODULE.evidence(self.reg_path) if self.reg_path.exists() else None,
            'tipOffsetEvidence': self.ev, 'surfaceEvidence': self.ev, 'padAvailabilityImage': self.ev,
            'pads': [],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def add_pair(self, resistor='R40', xs=(10.0, 10.5)):
        pads = [{'padId': resistor + '.1', 'rawPose': {'X': xs[0], 'Y': 11.0, 'Z': 58.3, 'A': 720.0}, 'authoredImageReview': {'reviewedMs': 123}} ,
                {'padId': resistor + '.2', 'rawPose': {'X': xs[1], 'Y': 11.0, 'Z': 58.3, 'A': 720.0}, 'authoredImageReview': {'reviewedMs': 124}}]
        self.target['pads'] = pads
        self.reg_path.write_text(json.dumps({'resistorPadMachineXYTargets': [
            {'padId': p['padId'], 'machineXYMm': [p['rawPose']['X'], p['rawPose']['Y']]}
            for p in pads]}, indent=2))
        self.target['registrationEvidence'] = MODULE.evidence(self.reg_path)

    def test_r40_pair_builds_decimal_gap_route_and_preserves_authored_fields(self):
        self.add_pair()
        original = json.loads(json.dumps(self.target))
        updated, stages, bounds, _, accounting = MODULE.build_route(self.raw, self.poses, self.target, 53.4)
        seq = updated['compensatedSequence']
        self.assertEqual(seq['authoredObservation'], original['compensatedSequence']['authoredObservation'])
        self.assertEqual(seq['conditioningFinishedMs'], 12345)
        self.assertEqual(seq['conditioningReportEvidence'], original['compensatedSequence']['conditioningReportEvidence'])
        self.assertEqual([p['padId'] for p in updated['pads']], ['R40.1', 'R40.2'])
        b = self.raw['B']
        for pad in updated['pads']:
            ri, di, rti, li = pad['restoreStageIndex'], pad['doseStageIndices'][0], pad['retractStageIndex'], pad['liftStageIndex']
            self.assertEqual([stages[i]['axis'] for i in (ri, di, rti, li)], ['B', 'B', 'B', 'Z'])
            deltas = [stages[ri]['target'] - b, stages[di]['target'] - stages[ri]['target'],
                      stages[rti]['target'] - stages[di]['target']]
            self.assertEqual(deltas, [-2, -4, 2])
            b = stages[rti]['target']
            self.assertEqual(stages[di]['dwellMilliseconds'], 300)
            self.assertEqual(stages[rti]['dwellMilliseconds'], 500)
            self.assertEqual(stages[ri]['estimatedGapMm'], 0.4)
            self.assertEqual(stages[li]['target'], 53.4)
        idle_ids = seq['finalIdleStageIndices']
        self.assertEqual(len(idle_ids), 2)
        self.assertEqual(stages[idle_ids[0]]['target'] - b, 20)
        self.assertEqual(stages[idle_ids[1]]['target'] - stages[idle_ids[0]]['target'], 20)
        self.assertEqual([stages[i]['estimatedGapMm'] for i in idle_ids], [5.3, 5.3])
        self.assertEqual(stages[idle_ids[0]]['dwellMilliseconds'], 0)
        self.assertEqual(stages[idle_ids[1]]['dwellMilliseconds'], 2000)
        self.assertEqual(accounting, {'initialB': -1000.0, 'restoreDegrees': 4,
            'doseDegrees': -8, 'retractDegrees': 4, 'finalIdleDegrees': 40,
            'grossChargedDegrees': 56, 'finalB': -968.0})
        self.assertEqual(bounds['Z'], {'min': 53.4, 'max': 58.3})

    def test_any_same_resistor_pair_and_dose12_split_are_supported(self):
        self.add_pair('R1', (19.9, 20.0))
        self.target['compensatedSequence']['doseDegrees'] = 12
        self.target['compensatedSequence']['idleReliefDegrees'] = 20
        updated, stages, _, _, accounting = MODULE.build_route(self.raw, self.poses, self.target, 53.4)
        pads = updated['pads']
        self.assertEqual([len(p['doseStageIndices']) for p in pads], [2, 2])
        self.assertEqual([stages[i]['axis'] for i in pads[0]['doseStageIndices']], ['B', 'B'])
        self.assertEqual([stages[i]['target'] for i in pads[0]['doseStageIndices']], [-1008.0, -1014.0])
        self.assertEqual(updated['compensatedSequence']['finalIdleStageIndex'], len(stages) - 1)
        self.assertNotIn('finalIdleStageIndices', updated['compensatedSequence'])
        self.assertEqual(accounting['grossChargedDegrees'], 52)
        b = self.raw['B']
        deltas = []
        current = dict(self.raw)
        linear_steps = []
        for stage in stages:
            if stage['axis'] == 'B':
                deltas.append(stage['target'] - b)
                b = stage['target']
            else:
                if stage['axis'] in ('X', 'Y', 'Z'):
                    linear_steps.append((stage['axis'], abs(stage['target'] - current[stage['axis']])))
            current[stage['axis']] = stage['target']
        self.assertEqual(deltas, [-2, -6, -6, 2, -2, -6, -6, 2, 20])
        self.assertTrue(all(step <= (9.9 if axis in ('X', 'Y') else 4.9) + 1e-12 for axis, step in linear_steps))
        self.assertTrue(all(abs(stage['target'] * 100 - round(stage['target'] * 100)) < 1e-9
                            for stage in stages if stage['axis'] in ('X', 'Y', 'Z')))

    def test_different_resistors_and_invalid_lift_are_rejected(self):
        self.add_pair('R40')
        self.target['pads'][1]['padId'] = 'R39.2'
        with self.assertRaisesRegex(ValueError, 'one resistor'):
            MODULE.build_route(self.raw, self.poses, self.target, 53.4)
        self.add_pair('R40')
        self.target['surface']['rawZ'] = 58.31
        for pad in self.target['pads']:
            pad['rawPose']['Z'] = 58.31
        with self.assertRaisesRegex(ValueError, 'one stage'):
            MODULE.build_route(self.raw, self.poses, self.target, 53.4)


if __name__ == '__main__':
    unittest.main()
