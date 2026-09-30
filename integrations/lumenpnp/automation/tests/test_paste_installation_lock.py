import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('reviewed_action', Path(__file__).resolve().parents[1] / 'scripts/run_reviewed_action.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class PasteInstallationLockTests(unittest.TestCase):
    def test_missing_malformed_and_locked_block_legacy_actions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lock = root / 'automation/paste/installation-lock.json'
            lock.parent.mkdir(parents=True)
            for body in (None, '{', '[]', '{"schema":1,"locked":true}', '{"schema":1,"locked":0}', '{"schema":2,"locked":false}'):
                if body is not None:
                    lock.write_text(body)
                for action in ('home', 'pick', 'place', 'register', 'probe', 'review', 'vacuum'):
                    with self.assertRaises(RuntimeError):
                        module.check_paste_installation_lock(root, action)

    def test_only_explicit_false_releases(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lock = root / 'automation/paste/installation-lock.json'
            lock.parent.mkdir(parents=True)
            lock.write_text(json.dumps({'schema': 1, 'locked': False}))
            module.check_paste_installation_lock(root, 'pick')

    def test_paste_inspection_quarantine_and_staged_air_remain_routed(self):
        with tempfile.TemporaryDirectory() as folder:
            for action in module.PASTE_INSTALLATION_ACTIONS:
                module.check_paste_installation_lock(Path(folder), action)

if __name__ == '__main__':
    unittest.main()
