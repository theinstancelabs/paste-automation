"""Pure regex test and compile-only native runtime check; never initializes a machine."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeAirNashornTests(unittest.TestCase):
    @unittest.skipUnless(Path('/opt/openpnp/lib').is_dir(), 'Requires installed Nashorn libraries')
    def test_compile_only_runner_and_native_java_fault_pattern(self):
        with tempfile.TemporaryDirectory(prefix='air-policy-java-') as temporary:
            subprocess.run(['javac', '-d', temporary, str(ROOT/'tests/java/CheckNativeAir.java')], check=True, timeout=20)
            result = subprocess.check_output(['java', '-cp', temporary+':/opt/openpnp/lib/*', 'CheckNativeAir',
                str(ROOT/'paste/native-air.cjs'), str(ROOT/'scripts/Run_Paste_Air.js')], text=True, timeout=20)
        self.assertIn('15 cases', result)
        self.assertIn('without evaluation', result)


if __name__ == '__main__':unittest.main()
