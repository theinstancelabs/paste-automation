import importlib.util, json, tempfile, unittest, subprocess, hashlib, datetime
from pathlib import Path
spec=importlib.util.spec_from_file_location('reviewed_action',Path(__file__).resolve().parents[1]/'scripts/run_reviewed_action.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
ROOT=Path(__file__).resolve().parents[1]
build_spec=importlib.util.spec_from_file_location('fast_builder',ROOT/'paste/prepare-fast-camera-inspection.py')
builder=importlib.util.module_from_spec(build_spec);build_spec.loader.exec_module(builder)
class FastCameraPolicyTests(unittest.TestCase):
 def test_builder_derives_centered_fid_offset_and_pad2_from_bound_measurements(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);now=1790927000000;stamp=datetime.datetime.fromtimestamp(now/1000,datetime.timezone.utc).isoformat().replace('+00:00','Z');jvm=123;config='a'*64
   raw={'X':100.0,'Y':100.0,'Z':32.25,'A':200.0,'B':-4316.05};poses={k:{'x':1.0,'y':2.0,'z':3.0,'rotation':0.0} for k in ('N1','N2','top','bottom')}
   source={'id':'12345678-1234-1234-1234-123456789abc','status':'completed-camera-survey-awaiting-image-review','motionSubmitted':True,'controllerPositionVerified':True,'uncertainCompletion':False,'request':{'id':'12345678-1234-1234-1234-123456789abc','jvmStartMs':jvm,'liveConfigurationSha256':config},'afterQuerySnapshot':{'raw':raw,'driver':dict(raw),'nativePoses':poses}}
   sp=root/'source.json';sp.write_text(json.dumps(source))
   board=builder.ROOT/'pnp/pcb/ftp/ftp.kicad_pcb';reg={'scope':'offline-native-fresh-ftp-two-fiducial-transform-with-third-point-check','acceptance':{'passed':True},'machineConfigurationChanged':False,'jobChanged':False,'board':{'sha256':hashlib.sha256(board.read_bytes()).hexdigest()},'measurements':{'FID2':{'measuredTopCameraXYMm':[100.0,100.0]}},'resistorPadMachineXYTargets':[{'padId':'R1.1','machineXYMm':[110.0,111.0]},{'padId':'R1.2','machineXYMm':[112.0,113.0]}]};rp=root/'registration.json';rp.write_text(json.dumps(reg))
   image=root/'top-raw.png';image.write_bytes(b'\x89PNG\r\n\x1a\ntest');ih=hashlib.sha256(image.read_bytes()).hexdigest()
   detection={'reference':'FID2','detectedMachineXYMm':[100.1,100.05]};axes={k:{'model':v,'driver':v} for k,v in raw.items()};center={'schema':1,'scope':'native-current-pose-fiducial-vision','status':'completed-native-fiducial-detection-awaiting-review','requestId':'22345678-1234-1234-1234-123456789abc','finishedAt':stamp,'jvmStartMs':jvm,'liveConfigurationBeforeSha256':config,'liveConfigurationAfterSha256':config,'reference':'FID2','nativeFiducialDetection':detection,'nativePose':{'rawAxes':axes},'camera':{'locationMm':{'x':100.0,'y':100.0}},'images':{'raw':{'path':image.name,'sha256':ih}},'physicalRegistrationEstablished':False,'noMotion':True,'noActuation':True,'noVacuum':True,'jobSaved':False,'configurationSaved':False,'modelPoseUnchanged':True,'configurationRestored':True};cp=root/'center.json';cp.write_text(json.dumps(center))
   fid=builder.build(sp,rp,builder.JOB,['FID2'],'Root','Reviewed synthetic bounded FID2 sample',None,'midpoint',now,fiducial_sample='xplus',fiducial_centering_report=cp)
   self.assertEqual(fid['targets'][0]['sample'],'xplus');self.assertEqual(fid['targets'][0]['offsetXYMm'],[1.0,0.0]);self.assertAlmostEqual(fid['targets'][0]['x'],101.1);self.assertAlmostEqual(fid['targets'][0]['y'],100.05);self.assertEqual(fid['fiducialCenteringReport']['sha256'],hashlib.sha256(cp.read_bytes()).hexdigest())
   pad=builder.build(sp,rp,builder.JOB,['R1'],'Root','Reviewed synthetic R1 pad2 target',None,'pad2',now)
   self.assertEqual((pad['targets'][0]['x'],pad['targets'][0]['y']),(112.0,113.0))
   affine=dict(reg);affine['scope']='offline-fresh-ftp-three-fiducial-affine-with-held-out-pad-checks';afp=root/'accepted-affine-registration.json';afp.write_text(json.dumps(affine))
   affine_pad=builder.build(sp,afp,builder.JOB,['R1'],'Root','Reviewed synthetic affine pad2 target',None,'pad2',now)
   self.assertEqual((affine_pad['targets'][0]['x'],affine_pad['targets'][0]['y']),(112.0,113.0))
   with self.assertRaisesRegex(ValueError,'Fiducial sampling requires'):
    builder.build(sp,afp,builder.JOB,['FID2'],'Root','No FID offsets from affine source',None,'midpoint',now)
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
 def test_no_motion_inspection_loader_allowed_under_intact_lock(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);p=root/'automation/paste/installation-lock.json';p.parent.mkdir(parents=True);p.write_text('{"schema":1,"locked":true}')
   module.check_paste_installation_lock(root,'load-fast-camera-inspection')
   p.write_text('{')
   with self.assertRaises(RuntimeError):module.check_paste_installation_lock(root,'load-fast-camera-inspection')
 def test_nashorn_policy_uses_synthetic_stubs_only(self):
  with tempfile.TemporaryDirectory() as td:
   subprocess.run(['javac','-d',td,str(ROOT/'tests/java/EvaluateFastCameraPolicy.java'),str(ROOT/'tests/java/CheckNativeAir.java')],check=True,timeout=20)
   result=subprocess.check_output(['java','-cp',td+':/opt/openpnp/lib/*','EvaluateFastCameraPolicy',str(ROOT/'paste/fast-camera-inspection.cjs'),str(ROOT/'tests/java/fast-camera-policy-fixtures.js')],text=True,timeout=20)
   self.assertIn('synthetic route/lock stubs passed',result)
   for script in ('Fast_Camera_Inspection.js','Load_Registered_Inspection_Job.js'):
    subprocess.check_call(['java','-cp',td+':/opt/openpnp/lib/*','CheckNativeAir',str(ROOT/'paste/native-air.cjs'),str(ROOT/'scripts'/script)],timeout=20)
if __name__=='__main__':unittest.main()
