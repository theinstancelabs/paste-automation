from pathlib import Path
import importlib.util
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reviewed_action', ROOT / 'scripts/run_reviewed_action.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class CalibrationInvalidationDispatchTests(unittest.TestCase):
    def test_action_map_allowlists_and_script_are_consistent(self):
        action = 'operator-invalidate-calibration'
        dispatcher = (ROOT / 'scripts/Automation_Reviewed_Command.js').read_text()
        match = re.search(r"'operator-invalidate-calibration':'([^']+)'", dispatcher)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'Run_Operator_Invalidate_Calibration.js')
        self.assertTrue((ROOT / 'scripts' / match.group(1)).is_file())
        self.assertIn(action, module.ACTION_ALLOWLIST)
        self.assertIn(action, module.PASTE_INSTALLATION_ACTIONS)
        busy_gate = dispatcher.split('if(!actions[q.action]', 1)[1].split('))throw new Error', 1)[0]
        self.assertNotIn(action, busy_gate)
        with tempfile.TemporaryDirectory() as folder:
            module.check_paste_installation_lock(Path(folder), action)

    def test_prime_segment_dispatch_is_profile_bounded_and_installation_locked(self):
        action='operator-prime-segment'
        dispatcher=(ROOT/'scripts/Automation_Reviewed_Command.js').read_text()
        match=re.search(r"'operator-prime-segment':'([^']+)'",dispatcher)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1),'Run_Operator_Prime_Segment.js')
        script=(ROOT/'scripts'/match.group(1)).read_text()
        self.assertIn('api.primeSegment(q)',script)
        self.assertIn('q.degrees<1||q.degrees>10',script)
        self.assertIn(action,module.ACTION_ALLOWLIST)
        self.assertIn(action,module.PASTE_INSTALLATION_ACTIONS)
        installation_gate=dispatcher.split("if(['operator-prime-segment'",1)[1].split("].indexOf(q.action)<0)",1)[0]
        self.assertNotEqual(installation_gate,'')
        with tempfile.TemporaryDirectory() as folder:
            module.check_paste_installation_lock(Path(folder),action)

if __name__ == '__main__':
    unittest.main()
