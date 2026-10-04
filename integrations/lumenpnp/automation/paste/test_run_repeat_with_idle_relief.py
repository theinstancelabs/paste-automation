import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name('run-repeat-with-idle-relief.py')
SPEC = importlib.util.spec_from_file_location('repeat_with_idle_relief', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TestRepeatWithIdleRelief(unittest.TestCase):
    def test_preflight_reserves_relief_after_batch(self):
        with self.assertRaisesRegex(RuntimeError, 'Combined batch and post-run relief'):
            MODULE.validate_preflight_budget({'remainingAfter': 14.99}, 15, 15)

    def test_preflight_bounds_total_pending_to_relief_api_cap(self):
        with self.assertRaisesRegex(RuntimeError, '300-degree cap'):
            MODULE.validate_preflight_budget({'remainingAfter': 50}, 286, 15)

    def test_profile_change_after_batch_blocks_first_relief_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            profile_path = Path(temporary) / 'profile.json'
            original = {'id': 'profile-a', 'sessionId': 'session-a', 'safeZ': 32.25}
            profile_path.write_text(json.dumps(original))
            binding = MODULE.profile_binding(profile_path)
            changed = {**original, 'sessionId': 'session-b'}
            profile_path.write_text(json.dumps(changed))

            with patch.object(MODULE, 'verified_relief_step') as dispatch:
                with self.assertRaisesRegex(RuntimeError, 'Profile/session changed after the batch'):
                    MODULE.run_post_run_relief(profile_path, binding, 15, 1)
                dispatch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
