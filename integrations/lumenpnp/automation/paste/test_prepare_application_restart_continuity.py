import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('prepare-contiguous-batch.py')
spec = importlib.util.spec_from_file_location('prepare_contiguous_batch', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RestartBindingTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            'sessionId': 'session',
            'liveConfigurationSha256': 'a' * 64,
            'transitions': [
                {'oldJvmStartMs': 10, 'newJvmStartMs': 20},
                {'oldJvmStartMs': 20, 'newJvmStartMs': 30},
            ],
        }
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'continuity.json'
        self.path.write_text(json.dumps(self.record))

    def tearDown(self):
        self.tmp.cleanup()

    def test_accepts_cli_path_and_derives_chain_summary(self):
        ref, summary = module.restart_binding(str(self.path), 'session', 'a' * 64, 30)
        self.assertEqual(ref['path'], str(self.path.resolve()))
        self.assertEqual(summary, {
            'sessionId': 'session', 'newJvmStartMs': 30,
            'liveConfigurationSha256': 'a' * 64, 'allowedJvmStartMs': [10, 20, 30],
        })

    def test_rejects_wrong_identity_jvm_or_bad_path(self):
        for session, config, jvm in [
            ('other', 'a' * 64, 30), ('session', 'b' * 64, 30), ('session', 'a' * 64, 31),
        ]:
            with self.subTest(session=session, config=config, jvm=jvm):
                with self.assertRaises(ValueError):
                    module.restart_binding(str(self.path), session, config, jvm)
        with self.assertRaises(Exception):
            module.restart_binding(str(self.path) + '.missing', 'session', 'a' * 64, 30)


if __name__ == '__main__':
    unittest.main()
