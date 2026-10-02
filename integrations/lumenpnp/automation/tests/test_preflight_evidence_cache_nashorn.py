"""Run the native evidence-reader cache against Nashorn; never loads OpenPnP or a machine."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PreflightEvidenceCacheNashornTests(unittest.TestCase):
    @unittest.skipUnless(Path('/opt/openpnp/lib').is_dir(), 'Requires installed Nashorn libraries')
    def test_real_native_reader_functions_recheck_hash_and_reuse_frozen_json(self):
        with tempfile.TemporaryDirectory(prefix='preflight-evidence-cache-') as temporary:
            subprocess.run([
                'javac', '-d', temporary,
                str(ROOT / 'tests/java/EvaluatePreflightEvidenceCache.java'),
            ], check=True, timeout=20)
            result = subprocess.check_output([
                'java', '-cp', temporary + ':/opt/openpnp/lib/*',
                'EvaluatePreflightEvidenceCache',
                str(ROOT / 'scripts/Commission_Paste_Contiguous_Batch.js'),
            ], text=True, timeout=20)
        self.assertIn('repeated hash, immutable reuse, and changed-file rejection', result)


if __name__ == '__main__':
    unittest.main()
