import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('prepared_batch_runner', ROOT/'automation/paste/run-prepared-contiguous-batch.py')
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

class TerminalWaitSecondsTest(unittest.TestCase):
    def test_wide_authoring_scope_has_longer_observation_window(self):
        self.assertEqual(runner.terminal_wait_seconds('contiguous-native-ftp-selected-pads-up-to-40-preview'), 600)
        self.assertEqual(runner.terminal_wait_seconds('contiguous-native-ftp-selected-pads-preview'), 300)
        self.assertEqual(runner.terminal_wait_seconds('contiguous-native-scrap-batch'), 300)
        self.assertEqual(runner.terminal_wait_seconds('contiguous-native-scrap-batch-preview'), 300)
        self.assertEqual(runner.terminal_wait_seconds('unknown-scope'), 60)

class ExecuteImageFreshnessTest(unittest.TestCase):
    def test_requires_headroom_before_native_five_minute_gate(self):
        now = 1_800_000_000_000
        self.assertEqual(runner.validate_execute_image_freshness({'imageCapturedMs': now - 240_000}, now), 240_000)
        with self.assertRaisesRegex(ValueError, 'capture and review a new image'):
            runner.validate_execute_image_freshness({'imageCapturedMs': now - 240_001}, now)
        with self.assertRaisesRegex(ValueError, 'capture and review a new image'):
            runner.validate_execute_image_freshness({'imageCapturedMs': now + 1}, now)
        with self.assertRaisesRegex(ValueError, 'timestamp is missing'):
            runner.validate_execute_image_freshness({}, now)

    def test_expired_execute_is_rejected_before_finalization_or_dispatch(self):
        now = 1_800_000_000_000
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared = root/'prepared'
            prepared.mkdir()
            request = {'scope': 'contiguous-native-scrap-batch-preview', 'enabled': False,
                       'id': 'e901e8d2-e521-40e8-8d85-a1728928c531',
                       'imageCapturedMs': now - 240_001}
            (prepared/'preview-request.json').write_text(json.dumps(request))
            invoked = []
            with patch.object(runner.time, 'time', return_value=now/1000):
                with self.assertRaisesRegex(ValueError, 'capture and review a new image'):
                    runner.run(prepared, False, root=root,
                               invoke=lambda *args, **kwargs: invoked.append(args))
            self.assertEqual(invoked, [])
            self.assertFalse((prepared/'runner-execute-attempt.json').exists())
            self.assertFalse((root/'automation/plans/paste-contiguous-batch-request.json').exists())

if __name__ == '__main__':
    unittest.main()
