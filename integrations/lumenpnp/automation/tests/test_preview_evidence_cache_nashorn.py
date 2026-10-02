"""Run the preview evidence-reader cache in Nashorn; never initializes OpenPnP or a machine."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PreviewEvidenceCacheNashornTests(unittest.TestCase):
    @unittest.skipUnless(Path('/opt/openpnp/lib').is_dir(), 'Requires installed Nashorn libraries')
    def test_real_preview_readers_recheck_hash_and_reuse_frozen_json(self):
        with tempfile.TemporaryDirectory(prefix='preview-evidence-cache-') as temporary:
            subprocess.run([
                'javac', '-d', temporary,
                str(ROOT / 'tests/java/EvaluatePreviewEvidenceCache.java'),
            ], check=True, timeout=20)
            result = subprocess.check_output([
                'java', '-cp', temporary + ':/opt/openpnp/lib/*',
                'EvaluatePreviewEvidenceCache',
                str(ROOT / 'scripts/Preview_Paste_Contiguous_Batch.js'),
            ], text=True, timeout=20)
        self.assertIn('rehash, frozen reuse, changed-file rejection', result)


if __name__ == '__main__':
    unittest.main()
