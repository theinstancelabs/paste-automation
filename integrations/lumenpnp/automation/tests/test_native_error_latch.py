"""Installed native parser test using only a fresh disconnected object."""
from pathlib import Path
import subprocess
import tempfile
import unittest

AUTOMATION = Path(__file__).resolve().parents[1]
JAR = Path('/opt/openpnp/openpnp-gui-0.0.1-alpha-SNAPSHOT.jar')
CP = f'/opt/openpnp/lib/*:{JAR}'


class NativeErrorLatchTests(unittest.TestCase):
    @unittest.skipUnless(JAR.is_file(), 'Requires installed audited OpenPnP jar')
    def test_disconnected_native_response_cache_and_copy_on_write(self):
        with tempfile.TemporaryDirectory(prefix='offline-native-latch-') as directory:
            subprocess.run(['javac', '-cp', CP, '-d', directory,
                            str(AUTOMATION / 'tests/java/CheckNativeErrorLatch.java')],
                           check=True, timeout=20)
            output = subprocess.check_output(['java', '-Djava.awt.headless=true', '-cp', f'{directory}:{CP}',
                        'CheckNativeErrorLatch', str(AUTOMATION / 'paste/native-air.cjs')], text=True, timeout=20)
            self.assertIn('no communications opened', output)


if __name__ == '__main__':
    unittest.main()
