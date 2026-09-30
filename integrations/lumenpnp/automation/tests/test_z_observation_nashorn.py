"""Compile-only staged Z runtime/policy check. Never evaluates machine code."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
class ZObservationCompileTests(unittest.TestCase):
    @unittest.skipUnless(Path('/opt/openpnp/lib').is_dir(), 'Installed Nashorn required')
    def test_compile_without_evaluation(self):
        with tempfile.TemporaryDirectory(prefix='z-observation-compile-') as temporary:
            subprocess.run(['javac','-d',temporary,str(ROOT/'tests/java/CheckNativeAir.java')],check=True,timeout=20)
            for source in ['scripts/Observe_Paste_B.js','paste/b-dose.cjs','scripts/Survey_Paste_Coupon.js','scripts/Observe_Paste_Z.js','paste/z-observation.cjs','scripts/Install_Paste_Error_Latch.js','paste/error-latch-install.cjs','scripts/Automation_Reviewed_Command.js','scripts/Read_Paste_Position_Barrier.js','paste/position-barrier.cjs','scripts/Configure_Paste_B_Axis.js','paste/b-axis-configuration.cjs','scripts/Commission_Paste_B_Stroke.js','scripts/Preview_Paste_Commissioning_Stroke.js','paste/commissioning-stroke.cjs']:
                output=subprocess.check_output(['java','-cp',temporary+':/opt/openpnp/lib/*','CheckNativeAir',str(ROOT/'paste/native-air.cjs'),str(ROOT/source)],text=True,timeout=20)
                self.assertIn('without evaluation',output)
