import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SCRIPT=Path(__file__).with_name('wipe-towel-side-to-side.py')
spec=importlib.util.spec_from_file_location('wipe',SCRIPT)
wipe=importlib.util.module_from_spec(spec);spec.loader.exec_module(wipe)
NOW=1790000000000

class WipeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.raw={'X':10,'Y':20,'Z':58.75,'A':200,'B':720};self.poses={k:{'x':1,'y':2,'z':3,'rotation':4} for k in ('N1','N2','top','bottom')}
  q={'id':'12345678-1234-1234-1234-123456789abc','scope':'read-only-native-position-barrier','jvmStartMs':NOW-10000,'liveConfigurationSha256':'a'*64}
  self.source=self.root/'source.json';self.source.write_text(json.dumps({'schema':1,'id':q['id'],'request':q,'status':'completed-read-only-position-barrier','noMotionCommandSubmitted':True,'controllerPositionVerified':True,'uncertainCompletion':False,'liveConfigurationSha256':'a'*64,'reported':self.raw,'afterQuerySnapshot':{'raw':self.raw,'driver':self.raw,'nativePoses':self.poses}}))
  self.image=self.root/'image.png';self.image.write_bytes(b'\x89PNG\r\n\x1a\nimage');os.utime(self.image,ns=((NOW-1000)*1000000,)*2)
 def build(self,**kw):
  opts={'clearance_z':32.25,'now_ms':NOW};opts.update(kw)
  return wipe.build(self.source,self.image,'Reviewed full towel corridor at start pose',**opts)
 def test_preview_is_dispatch_free_and_route_returns_center_with_fixed_axes(self):
  p=self.build();self.assertFalse(p['dispatchPerformed']);self.assertEqual(p['cycles'],3)
  steps=p['route']['steps'];self.assertEqual(steps[-1]['after']['X'],self.raw['X'])
  self.assertTrue(all(s['after'][a]==self.raw[a] for s in steps for a in ('Y','Z','A','B')))
 def test_bounded_parameters_and_lift_representation(self):
  for kwargs in ({'halfspan':0},{'halfspan':1.01},{'cycles':0},{'cycles':6},{'clearance_z':58.75}):
   with self.assertRaises(ValueError):self.build(**kwargs)
  with self.assertRaises(ValueError):wipe.lift_steps(26.5,26.37)
  self.assertEqual(wipe.lift_steps(26.5,20),[-5,-1,-.5])
 def test_machine_commissioning_envelope_is_forwarded_exactly(self):
  envelope={'schema':1,'configHash':'a'*64,'maximumMm':432.0,'basis':{'openPnpConfiguredHighMm':440.0}}
  captured=[]
  original_builder=getattr(wipe.route.prepare,'commissioning_envelope',None)
  original_plan=wipe.route.plan
  try:
   wipe.route.prepare.commissioning_envelope=lambda config: envelope
   def plan(spec,now=None):
    captured.append(spec)
    return {'steps':[],'commissioningEnvelope':spec.get('commissioningEnvelope')}
   wipe.route.plan=plan
   result=self.build()
   self.assertEqual(captured[0]['commissioningEnvelope'],envelope)
   self.assertEqual(result['route']['commissioningEnvelope'],envelope)
  finally:
   wipe.route.plan=original_plan
   if original_builder is None:delattr(wipe.route.prepare,'commissioning_envelope')
   else:wipe.route.prepare.commissioning_envelope=original_builder

 def test_one_way_x_and_y_preserve_other_axes(self):
  for axis,stroke in [('X',-4),('Y',2)]:
   p=self.build(axis=axis,stroke_mm=stroke)
   self.assertEqual(p['routeSpec']['waypoints'],[{'axis':axis,'targetMm':self.raw[axis]+stroke}])
   self.assertEqual(p['mode'],'one-way-stroke')
   self.assertFalse(p['dispatchPerformed'])
   for step in p['route']['steps']:
    for fixed in set(self.raw)-{axis}: self.assertEqual(step['after'][fixed],self.raw[fixed])
 def test_one_way_rejects_invalid_or_mixed_parameters(self):
  for kw in [{'stroke_mm':0},{'stroke_mm':4.01},{'stroke_mm':float('nan')},{'stroke_mm':1,'halfspan':.5},{'stroke_mm':1,'cycles':3},{'axis':'B','stroke_mm':1}]:
   with self.assertRaises(ValueError): self.build(**kw)

 def test_route_failure_never_calls_lift(self):
  p=self.build(clearance_z=53.75);calls=[];(self.root/'automation/evidence').mkdir(parents=True)
  def failed(*a,**kw):raise RuntimeError('synthetic route failure')
  with self.assertRaises(RuntimeError):wipe.execute(p,self.root,failed,lambda *a:calls.append(a))
  self.assertEqual(calls,[])

if __name__=='__main__':unittest.main()
