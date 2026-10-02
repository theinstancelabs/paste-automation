import importlib.util, json, tempfile, unittest, subprocess
from pathlib import Path
spec=importlib.util.spec_from_file_location('reviewed_action',Path(__file__).resolve().parents[1]/'scripts/run_reviewed_action.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
ROOT=Path(__file__).resolve().parents[1]
build_spec=importlib.util.spec_from_file_location('fast_builder',ROOT/'paste/prepare-fast-camera-inspection.py')
builder=importlib.util.module_from_spec(build_spec);build_spec.loader.exec_module(builder)
class FastCameraPolicyTests(unittest.TestCase):
 def test_python_dispatch_requires_dedicated_policy_and_preserves_locked_state(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);d=root/'automation/paste';d.mkdir(parents=True)
   (d/'installation-lock.json').write_text('{"schema":1,"locked":true}')
   good=json.loads((ROOT/'paste/camera-inspection-policy.json').read_text());(d/'camera-inspection-policy.json').write_text(json.dumps(good))
   module.check_paste_installation_lock(root,'paste-fast-camera-inspection')
   for bad in ({**good,'maxSegmentMm':11},{**good,'noPasteActuation':False},{}):
    (d/'camera-inspection-policy.json').write_text(json.dumps(bad))
    with self.assertRaises(RuntimeError):module.check_paste_installation_lock(root,'paste-fast-camera-inspection')
   (d/'camera-inspection-policy.json').write_text(json.dumps(good));(d/'installation-lock.json').write_text('{')
   with self.assertRaises(RuntimeError):module.check_paste_installation_lock(root,'paste-fast-camera-inspection')
 def test_terminal_source_allowlist_supports_chaining_only_certain_report_families(self):
  self.assertEqual(builder.TERMINAL_SOURCE_STATUSES,{'completed-contiguous-air-batch-awaiting-observation','completed-contiguous-batch-awaiting-observation','completed-camera-survey-awaiting-image-review'})
 def test_firmware_reporting_grid_quantization(self):
  self.assertEqual(builder.report_grid(10.0049),10.0)
  self.assertEqual(builder.report_grid(10.005),10.01)
  self.assertEqual(builder.report_grid(-10.0049),-10.0)
 def test_existing_global_lock_remains_locked(self):
  module.check_paste_installation_lock(ROOT.parent,'paste-fast-camera-inspection')
 def test_nashorn_policy_uses_synthetic_stubs_only(self):
  with tempfile.TemporaryDirectory() as td:
   subprocess.run(['javac','-d',td,str(ROOT/'tests/java/EvaluateFastCameraPolicy.java')],check=True,timeout=20)
   result=subprocess.check_output(['java','-cp',td+':/opt/openpnp/lib/*','EvaluateFastCameraPolicy',str(ROOT/'paste/fast-camera-inspection.cjs'),str(ROOT/'tests/java/fast-camera-policy-fixtures.js')],text=True,timeout=20)
   self.assertIn('synthetic route/lock stubs passed',result)
if __name__=='__main__':unittest.main()
