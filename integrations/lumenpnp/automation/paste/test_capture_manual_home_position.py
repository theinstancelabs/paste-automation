import importlib.util
from pathlib import Path
import unittest

SCRIPT=Path(__file__).with_name('capture-manual-home-position.py')
spec=importlib.util.spec_from_file_location('capture_manual_home_position',SCRIPT)
capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)

class CaptureManualHomeTests(unittest.TestCase):
    def test_busy_model_fails_fast(self):
        with self.assertRaisesRegex(RuntimeError,'machine busy'):
            capture.ensure_model_idle({'busy':True})

    def test_idle_model_passes(self):
        capture.ensure_model_idle({'busy':False})

if __name__=='__main__': unittest.main()
