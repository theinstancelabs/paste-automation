import importlib.util, json, os, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
SCRIPT=Path(__file__).with_name('author-no-b-scrap-wipe.py')
SPEC=importlib.util.spec_from_file_location('author_no_b_scrap_wipe',SCRIPT)
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)

class NoBScrapWipeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=1_800_000_000_000
  self.session={'sessionId':'test-session','jvmStartMs':123,'liveConfigurationSha256':'a'*64,'syringeId':'test-syringe'}
  self.raw={'X':310.09,'Y':318.10,'Z':53.45,'A':720.0,'B':-2889.0}
  self.template=self.json('template.json',self.session)
  self.barrier=self.json('barrier.json',{'status':'completed-read-only-position-barrier','controllerPositionVerified':True,'noMotionCommandSubmitted':True,'uncertainCompletion':False,'finishedAt':self.ts(self.now-1000),'request':{'jvmStartMs':123},'liveConfigurationSha256':'a'*64,'afterQuerySnapshot':{'raw':self.raw,'nativePoses':{'N1':{'x':100.0,'y':200.0,'z':20.0},'N2':{'x':100.0,'y':200.0,'z':43.0},'top':{'x':1.0,'y':1.0,'z':1.0},'bottom':{'x':2.0,'y':2.0,'z':2.0}}}})
  self.image=self.root/'top.png';self.image.write_bytes(b'\x89PNG\r\n\x1a\ntest');os.utime(self.image,ns=((self.now-1000)*1_000_000,(self.now-1000)*1_000_000))
  self.profile=self.json('profile.json',{**self.session,'provenance':'commissioning-provisional','precisionCalibrated':False,'flowCalibrated':False,'estimatedGapMm':.5,'gapUncertaintyMm':.3,'basis':'original profile base'})
  self.previous=self.json('previous.json',{'ok':True});self.ledger=self.json('ledger.json',{'ok':True})
  self.q={'schema':1,'scope':'reviewed-no-b-scrap-wipe-inputs','reviewedBy':'operator','reviewedMs':self.now-500,'reviewBasis':'Reviewed the clean bare scrap area and short strand path.','profileBasis':'Temporary conditional local tip-to-scrap gap estimate.','startRaw':self.raw,'sources':{k:M.ev(v) for k,v in [('template',self.template),('barrier',self.barrier),('image',self.image),('profileBase',self.profile),('previousReport',self.previous),('ledger',self.ledger)]},'wipe':{'axis':'X','deltaMm':1.5,'workRawZ':58.45,'clearanceRawZ':53.45,'estimatedGapMm':.4,'gapUncertaintyMm':.3},'attestations':dict(scrapOnly=True,bareScrapReviewed=True,bothHeadsClearanceReviewed=True,tipAndWipeReviewed=True,noBNoVacuumOrHoming=True,noFtpTargets=True)}
  self.inputs=self.json('inputs.json',self.q)
 def tearDown(self):self.tmp.cleanup()
 def ts(self,ms):return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat().replace('+00:00','Z')
 def json(self,name,obj):p=self.root/name;p.write_text(json.dumps(obj,indent=2)+'\n');return p
 def invoke(self,cmd,**kwargs):
  out=Path(cmd[cmd.index('--output')+1]);out.mkdir(parents=True);(out/'preview-request.json').write_text('{"enabled":false}\n');return SimpleNamespace(stdout=str(out/'preview-request.json'))
 def test_route_is_exactly_z_wipe_lift_no_b_and_disabled(self):
  with patch.object(M.subprocess,'run',side_effect=self.invoke):
   M.build(self.inputs,self.root/'prepared',now=self.now)
  recipe=json.loads((self.root/'prepared'/'recipe.json').read_text());review=json.loads((self.root/'prepared'/'clearance-review.json').read_text());profile=json.loads((self.root/'prepared'/'profile.json').read_text())
  self.assertEqual([(s['axis'],s['target']) for s in recipe['stages']],[('Z',58.45),('X',311.59),('Z',53.45)])
  self.assertTrue(recipe['stages'][1]['wipeReview']);self.assertEqual(recipe['stages'][1]['estimatedGapMm'],.4);self.assertEqual(profile['estimatedGapMm'],5.4);self.assertEqual(profile['rawPose']['Z'],53.45);self.assertFalse(any(s['axis']=='B' for s in recipe['stages']))
  self.assertEqual(review['attestations'],self.q['attestations']);self.assertFalse(json.loads((self.root/'prepared/prepared/preview-request.json').read_text())['enabled'])
 def test_rejects_unreviewed_scope_bad_gap_bad_endpoint_or_changed_source(self):
  for edit in [lambda q:q['attestations'].__setitem__('noBNoVacuumOrHoming',False),lambda q:q['wipe'].__setitem__('estimatedGapMm',.39),lambda q:q['wipe'].__setitem__('deltaMm',2.01),lambda q:q.__setitem__('startRaw',{**q['startRaw'],'B':-2888.0}),lambda q:q.__setitem__('targetSurface','ftp-selected-pads')]:
   q=json.loads(self.inputs.read_text());edit(q);p=self.json('bad.json',q)
   with self.assertRaises(ValueError):M.build(p,self.root/('out'+str(len(list(self.root.glob('out*'))))),now=self.now)
  q=json.loads(self.inputs.read_text());q['sources']['profileBase']['sha256']='0'*64;p=self.json('bad-hash.json',q)
  with self.assertRaises(ValueError):M.build(p,self.root/'bad-hash-out',now=self.now)
 def test_refuses_reused_output_directory(self):
  out=self.root/'same';out.mkdir()
  with self.assertRaises(FileExistsError):M.build(self.inputs,out,now=self.now)
if __name__=='__main__':unittest.main()
