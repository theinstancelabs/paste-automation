"""Compile-only Nashorn check for staged vacuum native adapter; never evaluates it."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VacuumProbeNativeCompileTests(unittest.TestCase):
    @unittest.skipUnless(Path('/opt/openpnp/lib').is_dir(), 'Installed OpenPnP Nashorn required')
    def test_adapter_and_contract_compile_without_evaluation(self):
        with tempfile.TemporaryDirectory(prefix='vacuum-probe-compile-') as temporary:
            subprocess.run(['javac', '-d', temporary, str(ROOT / 'tests/java/CheckNativeAir.java')], check=True, timeout=20)
            for source in ['scripts/Probe_Paste_Surface_By_Vacuum.js', 'paste/vacuum-probe-native.cjs', 'paste/vacuum-probe-policy.cjs']:
                output = subprocess.check_output(
                    ['java', '-cp', temporary + ':/opt/openpnp/lib/*', 'CheckNativeAir',
                     str(ROOT / 'paste/native-air.cjs'), str(ROOT / source)],
                    text=True, timeout=20)
                self.assertIn('without evaluation', output)


if __name__ == '__main__':
    unittest.main()
