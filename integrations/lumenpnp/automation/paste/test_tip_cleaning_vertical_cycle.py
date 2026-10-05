import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

SCRIPT=Path(__file__).with_name('tip-cleaning-vertical-cycle.py')
spec=importlib.util.spec_from_file_location('tip_cleaning_cycle',SCRIPT)
cycle=importlib.util.module_from_spec(spec);spec.loader.exec_module(cycle)
NOW=time.time_ns()//1_000_000

class CycleTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  for p in ('automation/evidence','.local-machine-backups'):(self.root/p).mkdir(parents=True)
  (self.root/'automation/plans').mkdir(parents=True)
  config={'softLowEnabled':False,'softLowMm':0,'softHighEnabled':False,'softHighMm':0,'safeLowEnabled':True,'safeLowMm':26.5,'safeHighEnabled':True,'safeHighMm':36.5}
  (self.root/'automation/plans/paste-z-observation-request.json').write_text(json.dumps({'nativeZConfiguration':config}))
  self.raw={'X':10.0,'Y':20.0,'Z':20.0,'A':200.0,'B':720.0}
  self.poses={k:{'x':1,'y':2,'z':3,'rotation':4} for k in ('N1','N2','top','bottom')}
  q={'id':'12345678-1234-1234-1234-123456789abc','scope':'read-only-native-position-barrier','jvmStartMs':NOW-10000,'liveConfigurationSha256':'a'*64}
  self.source=self.root/'source.json'
  self.source.write_text(json.dumps({'schema':1,'id':q['id'],'request':q,'status':'completed-read-only-position-barrier','noMotionCommandSubmitted':True,'controllerPositionVerified':True,'uncertainCompletion':False,'liveConfigurationSha256':'a'*64,'reported':self.raw,'afterQuerySnapshot':{'raw':self.raw,'driver':self.raw,'nativePoses':self.poses}}))
  self.image=self.root/'camera.png';self.image.write_bytes(b'\x89PNG\r\n\x1a\nimage');os.utime(self.image,ns=((NOW-1000)*1000000,)*2)
 def build(self,**kw):
  opts={'mode':'dip','target_z':20.5,'clearance_z':20.0,'dwell_ms':500,'review':'Reviewed centered vertical path and target','now_ms':NOW,'root':self.root};opts.update(kw)
  return cycle.build(self.source,self.image,**opts)
 def test_preview_has_explicit_vertical_steps_only_and_fixed_b(self):
  p=self.build();self.assertFalse(p['dispatchPerformed']);self.assertEqual(p['descentSteps'],[.5]);self.assertEqual(p['liftSteps'],[-.5]);self.assertEqual(p['fixedAxes']['B'],720.0)
 def test_clearance_equal_to_start_is_valid_and_returns_to_same_plane(self):
  self.raw['Z']=45.25
  self.source.write_text(json.dumps({**json.loads(self.source.read_text()),'reported':self.raw,'afterQuerySnapshot':{'raw':self.raw,'driver':self.raw,'nativePoses':self.poses}}))
  p=self.build(target_z=50.25,clearance_z=45.25)
  self.assertEqual(p['startZ'],p['clearanceZ']);self.assertEqual(p['descentSteps'],[5]);self.assertEqual(p['liftSteps'],[-5])
 def test_unreviewable_bounds_and_increments_reject(self):
  for kw in ({'target_z':20.0},{'clearance_z':20.6},{'target_z':20.13},{'target_z':22.0},{'dwell_ms':-1},{'dwell_ms':10001}):
   with self.assertRaises(ValueError):self.build(**kw)
 def test_evidence_remaining_lifetime_must_cover_worst_case_sequence(self):
  os.utime(self.image,ns=((NOW-60_000)*1_000_000,)*2)
  with self.assertRaisesRegex(ValueError,'remaining lifetime'):
   self.build()
 def test_execution_uses_z_only_and_preserves_b_through_dwell(self):
  p=self.build(target_z=21.0,clearance_z=20.0);calls=[];sleeps=[];pose=dict(self.raw)
  def runner(source,delta):
   calls.append(delta);pose['Z']+=delta
   path=self.root/f'report-{len(calls)}.json'
   path.write_text(json.dumps({'status':'completed-Z-observation-awaiting-image-review','uncertainCompletion':False,'controllerPositionVerified':True,'motionSubmitted':True,'nativeMotionCompletionReported':True,'request':{'axis':'Z','deltaMm':delta},'commandedControllerAxes':['Z'],'afterQuerySnapshot':{'raw':dict(pose)}}))
   return path
  result=cycle.execute(p,self.root,runner,sleep=sleeps.append)
  self.assertEqual(calls,[1,-1]);self.assertEqual(pose['B'],720.0);self.assertEqual(sleeps,[.5]);self.assertFalse(result['physicalAcceptanceEstablished'])
 def test_failed_descent_does_not_dwell_or_lift(self):
  p=self.build(target_z=21.0,clearance_z=20.0);calls=[];sleeps=[]
  def fail(*args):calls.append(args);raise RuntimeError('synthetic uncertain step')
  with self.assertRaises(RuntimeError):cycle.execute(p,self.root,fail,sleep=sleeps.append)
  self.assertEqual(len(calls),1);self.assertEqual(sleeps,[])
 def test_changed_soft_high_rejects_target_before_first_step(self):
  p=self.build(target_z=21.0,clearance_z=20.0);config=json.loads((self.root/'automation/plans/paste-z-observation-request.json').read_text())
  config['nativeZConfiguration']['softHighEnabled']=True;config['nativeZConfiguration']['softHighMm']=20.5
  (self.root/'automation/plans/paste-z-observation-request.json').write_text(json.dumps(config));calls=[]
  with self.assertRaisesRegex(ValueError,'soft-high'):
   cycle.execute(p,self.root,lambda *args:calls.append(args))
  self.assertEqual(calls,[])
 def test_missing_firmware_evidence_blocks_fine_step_before_runner(self):
  p=self.build();calls=[]
  with self.assertRaisesRegex(ValueError,'firmware-evidence'):
   cycle.execute(p,self.root,lambda *args:calls.append(args))
  self.assertEqual(calls,[])

if __name__=='__main__':unittest.main()
