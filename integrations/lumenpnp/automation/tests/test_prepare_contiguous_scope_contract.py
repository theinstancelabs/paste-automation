import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'prepare_contiguous_batch', ROOT / 'automation/paste/prepare-contiguous-batch.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class FinalizeScopeContractTest(unittest.TestCase):
    def test_minimum_travel_preview_can_be_finalized(self):
        self.assertIn('contiguous-native-ftp-minimum-travel-eight-pad-preview',
                      module.PREVIEW_SCOPES)

    def test_scope_allowlist_stays_explicit(self):
        self.assertEqual(len(module.PREVIEW_SCOPES), 10)
        self.assertNotIn('contiguous-native-ftp-minimum-travel-eight-pad',
                         module.PREVIEW_SCOPES)


if __name__ == '__main__':
    unittest.main()
