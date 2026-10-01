import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'prepare-purge-wipe-recipe.py'
SPEC = importlib.util.spec_from_file_location('purge_wipe_recipe', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PurgeWipeRecipeTests(unittest.TestCase):
    def setUp(self):
        self.raw = {'X': 283.46, 'Y': 319.76, 'Z': 58.25, 'A': 720, 'B': -1150}
        self.review = {'path': '/review.json', 'sha256': 'a' * 64}

    def test_prime_relief_wipe_lift_and_gross_net_accounting(self):
        stages = MODULE.recipe_stages(self.raw, self.review, 'X', -0.5, 53.25, 1.1, 1.0, 40, 20, 20)
        axes = [s['axis'] for s in stages]
        targets = [s['target'] for s in stages]
        self.assertEqual(axes, ['B', 'B', 'B', 'X', 'Z', 'B'])
        self.assertEqual(targets, [-1170, -1190, -1170, 282.96, 53.25, -1150])
        self.assertEqual([s.get('dwellMilliseconds') for s in stages if s['axis'] == 'B'], [0, 2000, 1000, 2000])
        self.assertEqual(stages[-1]['estimatedGapMm'], 6.1)
        b = [s['target'] for s in stages if s['axis'] == 'B']
        chain = [-1150] + b
        deltas = [right-left for left, right in zip(chain, chain[1:])]
        self.assertEqual(sum(abs(d) for d in deltas), 80)
        self.assertEqual(sum(deltas), 0)

    def test_unbalanced_b_recipe_is_recordable(self):
        stages = MODULE.recipe_stages(self.raw, self.review, 'Y', 0.5, 53.25, 1.1, 1.0, 40, 20, 0)
        b = [s['target'] for s in stages if s['axis'] == 'B']
        deltas = [right-left for left, right in zip([-1150] + b, b)]
        self.assertEqual(sum(deltas), -20)

    def test_gap_axis_and_wipe_inputs_fail_closed(self):
        for axis, delta, gap, uncertainty in (
            ('X', -0.5, 0.5, 0.4),
            ('Q', -0.5, 1.1, 1.0),
            ('X', 0, 1.1, 1.0),
            ('Y', 2.01, 1.1, 1.0),
        ):
            with self.subTest(axis=axis, delta=delta, gap=gap):
                with self.assertRaises(ValueError):
                    MODULE.recipe_stages(self.raw, self.review, axis, delta, 53.25, gap, uncertainty, 40, 20, 20)

    def test_review_timestamp_requires_finite_integer(self):
        now = 10_000_000
        MODULE.validate_review_time(now-1000, now)
        for value in (float('nan'), float('inf'), True, 1.5, now+1, now-300001):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    MODULE.validate_review_time(value, now)

    def test_output_is_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'recipe.json'
            MODULE.write_exclusive(path, {'schema': 1})
            with self.assertRaises(FileExistsError):
                MODULE.write_exclusive(path, {'schema': 1})


if __name__ == '__main__':
    unittest.main()
