import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('prepared_batch_runner', ROOT/'automation/paste/run-prepared-contiguous-batch.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

class TerminalWaitSecondsTest(unittest.TestCase):
    def test_wide_authoring_scope_has_longer_observation_window(self):
        self.assertEqual(runner.terminal_wait_seconds('contiguous-native-ftp-selected-pads-up-to-40-preview'), 600)
        self.assertEqual(runner.terminal_wait_seconds('contiguous-native-ftp-selected-pads-preview'), 300)
        self.assertEqual(runner.terminal_wait_seconds('unknown-scope'), 60)

if __name__ == '__main__':
    unittest.main()
