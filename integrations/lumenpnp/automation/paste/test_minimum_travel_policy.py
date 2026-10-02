import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name('minimum_travel_policy.py')
SPEC = importlib.util.spec_from_file_location('minimum_travel_policy', MODULE)
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)


class MinimumTravelPolicyTests(unittest.TestCase):
    def test_short_same_resistor_move_skips_matched_pair_and_keeps_lift_and_dose(self):
        plan = P.plan_minimum_travel_transitions([
            {'reference': 'R17', 'pad': '1', 'xy_mm': [10, 20]},
            {'reference': 'R17', 'pad': '2', 'xy_mm': [11.5, 20]},
        ])
        step = plan['transitions'][0]
        self.assertFalse(step['retractBeforeMove'])
        self.assertFalse(step['restoreAfterMove'])
        self.assertTrue(step['matchedRetractRestorePair'])
        self.assertTrue(step['preserveClearanceLift'])
        self.assertFalse(plan['doseChanged'])
        self.assertTrue(plan['endRunRetractRequired'])

    def test_threshold_is_strict_and_component_boundaries_always_retract(self):
        plan = P.plan_minimum_travel_transitions([
            {'reference': 'R17', 'pad': '1', 'xy_mm': [0, 0]},
            {'reference': 'R17', 'pad': '2', 'xy_mm': [2, 0]},
            {'reference': 'R18', 'pad': '1', 'xy_mm': [2.5, 0]},
        ])
        self.assertEqual([x['reason'] for x in plan['transitions']],
                         ['travel-at-or-above-limit', 'component-boundary'])
        self.assertTrue(all(x['retractBeforeMove'] and x['restoreAfterMove']
                            for x in plan['transitions']))

    def test_invalid_threshold_or_coordinates_rejected(self):
        with self.assertRaises(ValueError):
            P.plan_minimum_travel_transitions([], 0)
        with self.assertRaises(ValueError):
            P.plan_minimum_travel_transitions([
                {'reference': 'R1', 'pad': '1', 'xy_mm': [float('nan'), 0]},
            ])


if __name__ == '__main__':
    unittest.main()
