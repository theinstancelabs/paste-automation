from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LiftPasteConsoleTests(unittest.TestCase):
    def test_lift_dispatch_uses_guarded_console_api_without_r40_controls(self):
        script = (ROOT / 'scripts/Lift_Paste_Console.js').read_text()
        native = (ROOT / 'paste/operator-console-native.js').read_text()
        self.assertIn("typeof api.lift!=='function'", script)
        self.assertIn('s.busy||s.latched||s.error', script)
        self.assertIn('api.lift();', script)
        self.assertNotIn('JList', script)
        self.assertNotIn('getElementAt(39)', script)
        self.assertIn('lift:function(){return prepareThen(null);}', native)
        self.assertIn("submit('calibration-clearance-lift'", native)
        result = subprocess.run(['node', str(ROOT / 'paste/operator/test-native-return.cjs')],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
