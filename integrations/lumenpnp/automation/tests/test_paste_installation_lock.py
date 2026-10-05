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

    def test_fast_camera_job_load_is_allowed_while_installation_remains_locked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lock = root / 'automation/paste/installation-lock.json'
            lock.parent.mkdir(parents=True)
            lock.write_text(json.dumps({'schema': 1, 'locked': True}))
            module.check_paste_installation_lock(root, 'load-fast-camera-inspection')

    def test_paste_inspection_quarantine_and_staged_air_remain_routed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paste = root / 'automation/paste'
            paste.mkdir(parents=True)
            (paste / 'installation-lock.json').write_text(json.dumps({'schema': 1, 'locked': True}))
            (paste / 'camera-inspection-policy.json').write_text(json.dumps({
                'schema': 1, 'scope': 'camera-only-inspection-under-paste-installation-lock',
                'enabled': True, 'action': 'paste-fast-camera-inspection',
                'requiresInstallationLockPreserved': True, 'noPasteActuation': True,
                'topCameraXYOnly': True, 'n2Quarantined': True,
                'maxSegmentMm': 10, 'maxTotalTravelMm': 120,
            }))
            for action in module.PASTE_INSTALLATION_ACTIONS:
                module.check_paste_installation_lock(root, action)



if __name__ == '__main__':
    unittest.main()
