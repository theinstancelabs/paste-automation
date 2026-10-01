import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name('author-pressure-stabilization-sequence.py')
spec = importlib.util.spec_from_file_location('pressure_sequence', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PressureSequenceTests(unittest.TestCase):
    def test_authors_fixed_12_then_6_recipe_with_220_gross(self):
        raw = {'X': 300.0, 'Y': 200.0, 'Z': 58.45, 'A': 720.0, 'B': -3000.0}
        targets = {
            'wipe': {'X': 301.5, 'Y': 200.0},
            'conditioner': {'X': 302.5, 'Y': 200.0},
            'sacrificial': [{'X': 303 + i, 'Y': 201} for i in range(3)],
            'tests': [{'X': 303 + i, 'Y': 202} for i in range(3)],
        }
        stages, gross, final_raw = module.build_stages(raw, targets, {'path': '/review.json', 'sha256': 'a' * 64}, .4, .3)
        self.assertEqual(module.gap_at_work_height(.4, 58.45), .4)
        b = []
        current = raw['B']
        for stage in stages:
            if stage['axis'] == 'B':
                b.append(stage['target'] - current)
                current = stage['target']
        self.assertEqual(b, [-20, -20, -20, 20, -20, 2] +
                         [-2, -6, -6, 2] * 3 + [-2, -6, 2] * 3 + [20, 20])
        self.assertEqual(b[-2:], [20, 20])
        self.assertEqual(gross, 220)
        self.assertEqual(len(stages), 54)
        self.assertEqual(final_raw['Z'], module.CLEAR_Z)
        self.assertEqual(final_raw['A'], 720)
        self.assertEqual(final_raw['B'] - raw['B'], -72)
        self.assertTrue(all(s['target'] in (module.WORK_Z, module.CLEAR_Z) for s in stages if s['axis'] == 'Z'))

    def test_rejects_incomplete_or_reused_review_positions(self):
        raw = {'X': 300.0, 'Y': 200.0, 'Z': 58.45, 'A': 720.0, 'B': -3000.0}
        targets = {
            'wipe': {'X': 301.5, 'Y': 200.0}, 'conditioner': {'X': 302.5, 'Y': 200.0},
            'sacrificial': [{'X': 303 + i, 'Y': 201} for i in range(3)],
            'tests': [{'X': 303 + i, 'Y': 202} for i in range(3)],
        }
        targets['tests'][2] = dict(targets['tests'][1])
        with self.assertRaisesRegex(module.InputError, 'distinct'):
            module.build_stages(raw, targets, {'path': '/review.json', 'sha256': 'a' * 64}, .4, .3)


if __name__ == '__main__':
    unittest.main()
