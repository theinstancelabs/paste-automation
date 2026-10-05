import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

SCRIPT=Path(__file__).with_name('prepare-tip-cleaning-station-route.py')
spec=importlib.util.spec_from_file_location('prepare_tip_cleaning_route',SCRIPT)
planner=importlib.util.module_from_spec(spec);spec.loader.exec_module(planner)
NOW=time.time_ns()//1_000_000

class StationRouteTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.raw={'X':100.0,'Y':105.0,'Z':40.0,'A':200.0,'B':720.0}
  poses={k:{'x':1,'y':2,'z':3,'rotation':4} for k in ('N1','N2','top','bottom')}
  q={'id':'12345678-1234-1234-1234-123456789abc','scope':'read-only-native-position-barrier','jvmStartMs':NOW-10000,'liveConfigurationSha256':'a'*64}
  self.source=self.root/'source.json';self.source.write_text(json.dumps({'schema':1,'id':q['id'],'request':q,'status':'completed-read-only-position-barrier','noMotionCommandSubmitted':True,'controllerPositionVerified':True,'uncertainCompletion':False,'liveConfigurationSha256':'a'*64,'reported':self.raw,'afterQuerySnapshot':{'raw':self.raw,'driver':self.raw,'nativePoses':poses}}))
  self.image=self.root/'corridor.png';self.image.write_bytes(b'\x89PNG\r\n\x1a\nimage');os.utime(self.image,ns=((NOW-1000)*1_000_000,)*2)
  self.recipe=self.root/'station.json';self.recipe.write_text(json.dumps({'schema':1,'scope':'local-registered-tip-cleaning-station','fixedX':100.0,'transitZ':40.0,'stations':{'cup':{'y':105.0},'cloth':{'y':90.0}},'clothCycle':{'approachZ':41.0,'targetZ':42.0,'clearanceZ':41.0}}))
 def test_preview_moves_only_y_and_carries_exact_route_guards(self):
  p=planner.preview(self.source,self.image,self.recipe,'cloth','Reviewed complete station corridor',NOW)
  self.assertEqual(p['status'],'preview');self.assertFalse(p['dispatchPerformed'])
  self.assertEqual([s['axis'] for s in p['route']['steps']],['Y','Y'])
  self.assertEqual(p['route']['steps'][-1]['after']['Y'],90.0)
  self.assertEqual(p['route']['fixedAxes'],{'Z':40.0,'A':200.0,'B':720.0})
  self.assertEqual(p['routeSpec'].get('commissioningEnvelope'),None)
  self.assertEqual(p['verticalProfile'],{'approachZ':41.0,'targetZ':42.0,'clearanceZ':41.0})
 def test_fixed_x_and_transit_z_must_match_registration(self):
  wrong=json.loads(self.source.read_text());wrong['afterQuerySnapshot']['raw']['X']=100.03
  wrong['reported']['X']=100.03;wrong['afterQuerySnapshot']['driver']['X']=100.03;self.source.write_text(json.dumps(wrong))
  with self.assertRaisesRegex(ValueError,'will not move X'):
   planner.preview(self.source,self.image,self.recipe,'cloth','review',NOW)
  wrong['afterQuerySnapshot']['raw']['X']=100;wrong['reported']['X']=100;wrong['afterQuerySnapshot']['driver']['X']=100
  wrong['afterQuerySnapshot']['raw']['Z']=40.1;wrong['reported']['Z']=40.1;wrong['afterQuerySnapshot']['driver']['Z']=40.1;self.source.write_text(json.dumps(wrong))
  with self.assertRaisesRegex(ValueError,'transit height'):
   planner.preview(self.source,self.image,self.recipe,'cloth','review',NOW)
 def test_stale_image_and_at_station_do_not_create_motion_route(self):
  os.utime(self.image,ns=((NOW-301_000)*1_000_000,)*2)
  with self.assertRaisesRegex(ValueError,'Fresh'):
   planner.preview(self.source,self.image,self.recipe,'cloth','review',NOW)
  os.utime(self.image,ns=((NOW-1000)*1_000_000,)*2)
  p=planner.preview(self.source,self.image,self.recipe,'cup','review',NOW)
  self.assertEqual(p['status'],'already-at-station');self.assertFalse(p['dispatchPerformed'])
 def test_current_commissioning_envelope_is_carried_when_available(self):
  builder=getattr(planner.route.prepare,'commissioning_envelope',None)
  if not callable(builder): return
  envelope=planner.route.prepare.COMMISSIONING_ENVELOPE
  value=json.loads(self.source.read_text());value['request']['liveConfigurationSha256']=envelope['liveConfigurationSha256'];value['liveConfigurationSha256']=envelope['liveConfigurationSha256']
  self.source.write_text(json.dumps(value))
  p=planner.preview(self.source,self.image,self.recipe,'cloth','reviewed full corridor',NOW)
  self.assertEqual(p['routeSpec']['commissioningEnvelope'],envelope)
 def test_cloth_wiggle_stays_in_xy_corridor_and_returns_center(self):
  value=json.loads(self.source.read_text());raw=value['afterQuerySnapshot']['raw'];raw.update(X=100.0,Y=90.0,Z=52.25)
  value['reported']=dict(raw);value['afterQuerySnapshot']['driver']=dict(raw);self.source.write_text(json.dumps(value))
  recipe=json.loads(self.recipe.read_text());recipe['clothWiggleZ']=52.25;recipe['clothWiggleHalfspanMm']=1.0;recipe['clothWiggleCycles']=3;self.recipe.write_text(json.dumps(recipe))
  p=planner.preview(self.source,self.image,self.recipe,'cloth-wiggle','Reviewed full cloth corridor',NOW)
  self.assertFalse(p['dispatchPerformed']);self.assertFalse(p['physicalAcceptanceEstablished'])
  self.assertEqual([s['axis'] for s in p['route']['steps']],['X']*7)
  self.assertEqual([s['after']['X'] for s in p['route']['steps']][-1],100.0)
  self.assertTrue(all(s['after']['Y']==90.0 and s['after']['Z']==52.25 and s['after']['B']==720.0 for s in p['route']['steps']))
  self.assertEqual(p['fixedAxes'],['Y','Z','A','B'])
 def test_cloth_wiggle_requires_already_registered_height_and_bounded_parameters(self):
  recipe=json.loads(self.recipe.read_text());recipe.update(clothWiggleZ=52.25,clothWiggleHalfspanMm=1.0,clothWiggleCycles=3);self.recipe.write_text(json.dumps(recipe))
  with self.assertRaisesRegex(ValueError,'already be at registered'):
   planner.preview(self.source,self.image,self.recipe,'cloth-wiggle','review',NOW)
  value=json.loads(self.source.read_text());raw=value['afterQuerySnapshot']['raw'];raw.update(Y=90.0,Z=52.25)
  value['reported']=dict(raw);value['afterQuerySnapshot']['driver']=dict(raw);self.source.write_text(json.dumps(value))
  recipe['clothWiggleHalfspanMm']=1.01;self.recipe.write_text(json.dumps(recipe))
  with self.assertRaisesRegex(ValueError,'halfspan'):
   planner.preview(self.source,self.image,self.recipe,'cloth-wiggle','review',NOW)

 def test_cloth_stroke_is_one_signed_xy_step_without_return_or_z_b_motion(self):
  value=json.loads(self.source.read_text());raw=value['afterQuerySnapshot']['raw'];raw.update(X=100.0,Y=90.0,Z=43.5)
  value['reported']=dict(raw);value['afterQuerySnapshot']['driver']=dict(raw);self.source.write_text(json.dumps(value))
  recipe=json.loads(self.recipe.read_text());recipe.update(strokeAxis='Y',strokeMm=2.0,strokeRawZ=43.5);self.recipe.write_text(json.dumps(recipe))
  p=planner.preview(self.source,self.image,self.recipe,'cloth-stroke','Reviewed full cloth corridor',NOW)
  self.assertFalse(p['dispatchPerformed']);self.assertFalse(p['physicalAcceptanceEstablished'])
  self.assertEqual(p['routeSpec']['waypoints'],[{'axis':'Y','targetMm':92.0}])
  self.assertEqual(len(p['route']['steps']),1)
  self.assertEqual(p['route']['steps'][0]['axis'],'Y')
  self.assertEqual(p['route']['steps'][0]['after'],{'X':100.0,'Y':92.0,'Z':43.5,'A':200.0,'B':720.0})
  self.assertEqual(p['target'],{'X':100.0,'Y':92.0,'Z':43.5})
  self.assertEqual(p['fixedAxes'],['X','Z','A','B'])
  self.assertEqual(p['stroke'],{'axis':'Y','distanceMm':2.0,'returnsToStart':False})
  self.assertIsNone(p['verticalProfile'])
  self.assertIn('no return across the cloth track',p['nextStage'])

 def test_cloth_stroke_can_select_x_and_signed_direction(self):
  value=json.loads(self.source.read_text());raw=value['afterQuerySnapshot']['raw'];raw.update(X=100.0,Y=90.0,Z=43.5)
  value['reported']=dict(raw);value['afterQuerySnapshot']['driver']=dict(raw);self.source.write_text(json.dumps(value))
  recipe=json.loads(self.recipe.read_text());recipe.update(strokeAxis='X',strokeMm=-1.5,strokeRawZ=43.5);self.recipe.write_text(json.dumps(recipe))
  p=planner.preview(self.source,self.image,self.recipe,'cloth-stroke','review',NOW)
  self.assertEqual(p['routeSpec']['waypoints'],[{'axis':'X','targetMm':98.5}])
  self.assertEqual(p['route']['steps'][0]['after'],{'X':98.5,'Y':90.0,'Z':43.5,'A':200.0,'B':720.0})
  self.assertEqual(p['fixedAxes'],['Y','Z','A','B'])
  self.assertEqual(len(p['route']['steps']),1)

 def test_cloth_stroke_requires_exact_registered_start_and_bounded_recipe(self):
  value=json.loads(self.source.read_text());raw=value['afterQuerySnapshot']['raw'];raw.update(X=100.0,Y=90.0,Z=43.5)
  value['reported']=dict(raw);value['afterQuerySnapshot']['driver']=dict(raw);self.source.write_text(json.dumps(value))
  recipe=json.loads(self.recipe.read_text());recipe.update(strokeAxis='Y',strokeMm=1.0,strokeRawZ=43.5);self.recipe.write_text(json.dumps(recipe))
  for field,bad in (('X',100.001),('Y',90.001),('Z',43.501)):
   altered=json.loads(self.source.read_text());snapshot=altered['afterQuerySnapshot']['raw'];snapshot[field]=bad
   altered['reported']=dict(snapshot);altered['afterQuerySnapshot']['driver']=dict(snapshot);self.source.write_text(json.dumps(altered))
   with self.assertRaisesRegex(ValueError,'exactly match registered cloth'):
    planner.preview(self.source,self.image,self.recipe,'cloth-stroke','review',NOW)
   snapshot[field]=raw[field];altered['reported']=dict(snapshot);altered['afterQuerySnapshot']['driver']=dict(snapshot);self.source.write_text(json.dumps(altered))
  for axis,distance in (('B',1.0),('Y',0),('X',2.01),('Y',-2.01)):
   invalid=json.loads(self.recipe.read_text());invalid.update(strokeAxis=axis,strokeMm=distance,strokeRawZ=43.5);self.recipe.write_text(json.dumps(invalid))
   with self.assertRaises(ValueError): planner.preview(self.source,self.image,self.recipe,'cloth-stroke','review',NOW)

if __name__=='__main__':unittest.main()
