from pathlib import Path
import importlib.util
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reviewed_action', ROOT / 'scripts/run_reviewed_action.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FinePressureReliefDispatchTests(unittest.TestCase):
    def test_route_allowlists_busy_guard_and_installation_lock(self):
        action = 'operator-fine-pressure-relief'
        dispatcher = (ROOT / 'scripts/Automation_Reviewed_Command.js').read_text()
        match = re.search(r"'operator-fine-pressure-relief':'([^']+)'", dispatcher)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), 'Run_Operator_Fine_Pressure_Relief.js')
        self.assertTrue((ROOT / 'scripts' / match.group(1)).is_file())
        self.assertIn(action, module.ACTION_ALLOWLIST)
        self.assertIn(action, module.PASTE_INSTALLATION_ACTIONS)
        busy_gate = dispatcher.split('if(!actions[q.action]', 1)[1].split('))throw new Error', 1)[0]
        self.assertIn(action, busy_gate)
        installation_gate = dispatcher.split("if(['operator-prime-segment'", 1)[1].split('].indexOf(q.action)<0)', 1)[0]
        self.assertIn(action, installation_gate)
        with self.subTest('installation gate permits reviewed action under locked install'):
            import tempfile
            with tempfile.TemporaryDirectory() as folder:
                lock = Path(folder) / 'automation/paste/installation-lock.json'
                lock.parent.mkdir(parents=True)
                lock.write_text('{"schema":1,"locked":true}')
                module.check_paste_installation_lock(Path(folder), action)

    def test_adapter_is_fixed_one_degree_and_native_path_keeps_xyz_stationary(self):
        action_script = (ROOT / 'scripts/Run_Operator_Fine_Pressure_Relief.js').read_text()
        self.assertIn("api.relievePressure(1,1)", action_script)
        self.assertIn('s.busy||s.latched||s.error', action_script)
        self.assertNotIn('api.relievePressure(5,1)', action_script)
        # The native relief-path test executes reliefRun(1) against a fake B-only
        # motion adapter and asserts the XYZ anchor remains fixed.
        result = subprocess.run(['node', str(ROOT / 'paste/operator/test-native-relief.cjs')],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
