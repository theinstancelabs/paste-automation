from pathlib import Path
import importlib.util
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reviewed_action', ROOT / 'scripts/run_reviewed_action.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CalibratedGapDispatchTests(unittest.TestCase):
    def test_action_is_registered_and_allowed_under_installation_lock_but_not_while_busy(self):
        action = 'operator-set-calibrated-gap'
        dispatcher = (ROOT / 'scripts/Automation_Reviewed_Command.js').read_text()
        match = re.search(r"'operator-set-calibrated-gap':'([^']+)'", dispatcher)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'Set_Paste_Calibrated_Gap.js')
        self.assertIn(action, module.ACTION_ALLOWLIST)
        self.assertIn(action, module.PASTE_INSTALLATION_ACTIONS)
        busy_gate = dispatcher.split('if(!actions[q.action]', 1)[1].split('))throw new Error', 1)[0]
        self.assertNotIn(action, busy_gate)
        install_gate = dispatcher.split("if(['operator-prime-segment'", 1)[1].split('].indexOf(q.action)<0)', 1)[0]
        self.assertIn(action, install_gate)
        with tempfile.TemporaryDirectory() as folder:
            module.check_paste_installation_lock(Path(folder), action)

    def test_adapter_uses_current_gap_and_only_changes_gap_controls(self):
        script = (ROOT / 'scripts/Set_Paste_Calibrated_Gap.js').read_text()
        self.assertIn('api.calibrationStatus()', script)
        self.assertIn('c.ready!==true', script)
        self.assertIn('s.busy!==false', script)
        self.assertIn('s.latched!==false', script)
        self.assertIn("gap.setValue(new java.lang.Double(c.commandedGapMm))", script)
        self.assertIn("mode.setSelectedItem('gap')", script)
        self.assertNotIn('api.relievePressure', script)
        self.assertNotIn('api.purge', script)
        self.assertNotIn('Dose per pad', script)
        self.assertNotIn('Retraction between', script)


if __name__ == '__main__':
    unittest.main()
