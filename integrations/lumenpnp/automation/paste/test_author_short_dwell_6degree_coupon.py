import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name('author-short-dwell-6degree-coupon.py')
SPEC = importlib.util.spec_from_file_location('short_dwell_coupon', SCRIPT)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class ShortDwellCouponTests(unittest.TestCase):
    def setUp(self):
        self.raw = {'X': 276.48, 'Y': 298.80, 'Z': 58.45, 'A': 720, 'B': -3338}
        self.targets = {
            'wipe': {'X': 277.98, 'Y': 298.80},
            'conditioner': {'X': 276.48, 'Y': 301.48},
            'tests': [{'X': 280.22, 'Y': 301.48}, {'X': 283.42, 'Y': 301.48}, {'X': 286.63, 'Y': 301.48}],
        }

    def test_explicit_6_4_2_sweep_stays_under_existing_stage_cap_and_charges_194_gross(self):
        doses = M.parse_doses('6,4,2')
        stages, gross, final_raw = M.build_stages(self.raw, self.targets, {'path': '/review', 'sha256': 'a' * 64}, .4, .3, doses)
        cur = self.raw['B']; deltas = []
        for stage in stages:
            if stage['axis'] == 'B':
                delta = stage['target'] - cur
                deltas.append(delta)
                cur = stage['target']
        self.assertEqual(deltas, [-20, -20, -20, 20, -20, 6] + [-6, -6, 6, -6, -4, 6, -6, -2, 6] + [20, 20])
        self.assertEqual(gross, 194)
        self.assertEqual(final_raw['B'] - self.raw['B'], -26)
        self.assertEqual(final_raw['B'], -3364)
        self.assertEqual(len(stages), 32)
        self.assertLessEqual(len(stages), 40)
        b_dwells = [s['dwellMilliseconds'] for s in stages if s['axis'] == 'B']
        self.assertEqual(b_dwells, [0, 0, 2000, 1000, 2000, 500] + [0, 200, 500] * 3 + [0, 2000])
        self.assertEqual(M.number(.4, 'gap') - M.number(.3, 'uncertainty'), .10000000000000003)

    def test_explicit_4_4_4_repeat_recipe_charges_every_restore_and_retract(self):
        stages, gross, final_raw = M.build_stages(self.raw, self.targets, {'path': '/review', 'sha256': 'a' * 64}, .4, .3, [4, 4, 4])
        cur = self.raw['B']; deltas = []
        for stage in stages:
            if stage['axis'] == 'B':
                deltas.append(stage['target'] - cur)
                cur = stage['target']
        self.assertEqual(deltas, [-20, -20, -20, 20, -20, 6] + [-6, -4, 6] * 3 + [20, 20])
        self.assertEqual(gross, 194)
        self.assertEqual(final_raw['B'] - self.raw['B'], -26)
        self.assertEqual(
            [s['dwellMilliseconds'] for s in stages if s['axis'] == 'B'],
            [0, 0, 2000, 1000, 2000, 500] + [0, 200, 500] * 3 + [0, 2000],
        )

    def test_rejects_reused_or_too_far_wipe_and_reused_spot(self):
        bad = {**self.targets, 'wipe': {'X': self.raw['X'] + 2.01, 'Y': self.raw['Y']}}
        with self.assertRaisesRegex(M.InputError, 'Wipe point'):
            M.build_stages(self.raw, bad, {'path': '/review', 'sha256': 'a' * 64}, .4, .3, [6, 4, 2])
        bad = {**self.targets, 'tests': [self.targets['tests'][0], self.targets['tests'][0], self.targets['tests'][2]]}
        with self.assertRaisesRegex(M.InputError, 'distinct'):
            M.build_stages(self.raw, bad, {'path': '/review', 'sha256': 'a' * 64}, .4, .3, [6, 4, 2])

    def test_dose_parameter_is_explicit_and_closed_to_supported_values(self):
        for bad in ('', '6,4', '6,4,2,2', '6,3,2', '6.0,4,2'):
            with self.assertRaises(M.InputError):
                M.parse_doses(bad)


if __name__ == '__main__':
    unittest.main()
