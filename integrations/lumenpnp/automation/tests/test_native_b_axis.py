"""Native math only: isolated axes/planner/driver, no configuration or communications."""
from pathlib import Path
import subprocess
import tempfile
import unittest
AUTOMATION = Path(__file__).resolve().parents[1]
JAR = Path('/opt/openpnp/openpnp-gui-0.0.1-alpha-SNAPSHOT.jar')
CP = f'/opt/openpnp/lib/*:{JAR}'
class NativeBAxisTests(unittest.TestCase):
    @unittest.skipUnless(JAR.is_file(), 'Requires installed audited OpenPnP jar')
    def test_disconnected_partial_b_projection_and_feed(self):
        with tempfile.TemporaryDirectory(prefix='offline-native-b-') as directory:
            subprocess.run(['javac', '-cp', CP, '-d', directory,
                            str(AUTOMATION/'tests/java/CheckNativeBAxis.java')], check=True, timeout=20)
            output = subprocess.check_output(['java', '-Djava.awt.headless=true', '-cp', f'{directory}:{CP}',
                                              'CheckNativeBAxis'], text=True, timeout=20)
            self.assertIn('B719/B720/B721 preserved', output)
            self.assertIn('no communications opened', output)
