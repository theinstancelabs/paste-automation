import copy, importlib.util, json, tempfile, time, unittest
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
S=Path(__file__).with_name('author-conditioned-ftp-eight-pad.py');spec=importlib.util.spec_from_file_location('author_eight',S);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
class AuthorInputsTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  def write(n,v):
   p=self.root/n;p.write_bytes(v if isinstance(v,bytes) else json.dumps(v).encode());return M.EIGHT.ev(p)
  self.write=write;raw={'X':10,'Y':20,'Z':58.45,'A':720,'B':-1000};session={'sessionId':'test','jvmStartMs':1,'liveConfigurationSha256':'a'*64};self.raw=raw
  src={k:write(k+'.json',{}) for k in M.SOURCE_KEYS}
  src.update(template=write('template.json',session),barrier=write('barrier.json',{'afterQuerySnapshot':{'raw':raw}}),stationaryImage=write('stationary.jpg',b'\xff\xd8\xfftest'),tipImage=write('tip.jpg',b'\xff\xd8\xfftest'),surface=write('surface.json',{'surface':{'rawZ':58.3,'estimatedGapMm':.4,'gapUncertaintyMm':.3}}),tipOffset=write('tip.json',{'cameraMinusTipXYMm':[45.4,-64.49]}),scrapProfile=write('profile.json',{**session,'estimatedGapMm':.4,'gapUncertaintyMm':.3}),scrapExperiment=write('experiment.json',{'schema':1,'scope':'reviewed-scrap-retraction-coupon','mode':'transfer-preparation','startRaw':{'B':123},'workRawZ':58.45,'clearanceRawZ':53.45,'primeDegrees':60,'preWipeReliefDegrees':20,'conditioningDoseDegrees':20,'conditioningDwellMilliseconds':2000,'retractDegrees':2,'retractDwellMilliseconds':500}))
  src['registration']=write('registration.json',{'resistorPadMachineXYTargets':[{'padId':f'R{r}.{n}','machineXYMm':[100+r,200+n]} for r in range(1,5) for n in (1,2)]})
  now=int(time.time()*1000);report=write('camera.json',{'finishedAt':datetime.fromtimestamp((now-10)/1000,timezone.utc).isoformat()})
  self.q={'schema':1,'scope':'reviewed-eight-pad-authoring-inputs','reviewedBy':'test reviewer','reviewedMs':now,'reviewBasis':'Explicit synthetic complete-route physical review','profileBasis':'Explicit synthetic gap basis, no precision calibration','startRaw':raw,'doseDegrees':6,'surfaceRawZ':58.3,'xyClearanceRawZ':53.4,'scrapTargetsXY':[{'X':11,'Y':20},{'X':12,'Y':21}],'attestations':{k:True for k in M.ATTESTATIONS},'sources':src,'pairReviews':[{'reference':f'R{r}','padIds':[f'R{r}.2',f'R{r}.1'],'padIdentityReviewed':True,'padsAvailableReviewed':True,'reportEvidence':report,'imageEvidence':src['stationaryImage'],'capturedMs':now-10} for r in range(1,5)]}
 def tearDown(self):self.temp.cleanup()
 def load(self,e,json_value=True):
  b=Path(e['path']).read_bytes();return json.loads(b) if json_value else b
 def test_fresh_registration_does_not_require_or_retain_old_revalidation(self):
  q=copy.deepcopy(self.q);q['sources'].pop('registrationRevalidation');q['sources']['targetBase']=self.write('target-base-old.json',{'registrationRevalidationEvidence':{'path':'/stale/report.json','sha256':'0'*64}})
  _,_,_,target=M.derive(q,self.load,q['reviewedMs'])
  self.assertNotIn('registrationRevalidationEvidence',target)
 def test_derives_only_explicit_selection_preserves_inputs_and_pair_order(self):
  before=copy.deepcopy(self.q);e,r,p,t=M.derive(self.q,self.load,self.q['reviewedMs'])
  self.assertEqual(self.q,before);self.assertEqual(e['startRaw'],self.raw);self.assertEqual(e['primeDegrees'],60);self.assertEqual(t['reviewedMs'],self.q['reviewedMs']);self.assertEqual(r['reviewedMs'],self.q['reviewedMs']);self.assertEqual([x['padId'] for x in t['pads']][:2],['R1.2','R1.1']);self.assertEqual(t['pads'][0]['rawPose'],{'X':55.6,'Y':266.49,'Z':58.3,'A':720});self.assertEqual(p['estimatedGapMm'],.4);self.assertEqual(t['compensatedSequence']['doseDegrees'],6);self.assertEqual(t['registrationRevalidationEvidence'],self.q['sources']['registrationRevalidation'])
 def test_explicit_forward_dwell_defaults200_and_accepts_only200_1000_or2000(self):
  original=copy.deepcopy(self.q)
  self.assertEqual(M.derive(self.q,self.load,self.q['reviewedMs'])[3]['compensatedSequence']['dwellMilliseconds'],200)
  for wait in (200,1000,2000):
   q=copy.deepcopy(original);q['dwellMilliseconds']=wait;e,_,_,t=M.derive(q,self.load,q['reviewedMs']);self.assertEqual(t['compensatedSequence']['dwellMilliseconds'],wait);self.assertEqual(e['conditioningDwellMilliseconds'],2000)
  for wait in (True,200.0,500,0,2001):
   q=copy.deepcopy(original);q['dwellMilliseconds']=wait
   with self.assertRaises(ValueError):M.derive(q,self.load,q['reviewedMs'])
 def test_twenty_degree_option_retains_conditioner(self):
  self.q['doseDegrees']=20;self.q['dwellMilliseconds']=2000
  e,_,_,t=M.derive(self.q,self.load,self.q['reviewedMs'])
  self.assertEqual(t['compensatedSequence']['doseDegrees'],20)
  self.assertEqual(t['compensatedSequence']['dwellMilliseconds'],2000)
  self.assertEqual(e['conditioningDoseDegrees'],20)
  self.q['doseDegrees']=12
  self.assertEqual(M.derive(self.q,self.load,self.q['reviewedMs'])[3]['compensatedSequence']['doseDegrees'],12)
  self.q['doseDegrees']=8
  with self.assertRaises(ValueError):M.derive(self.q,self.load,self.q['reviewedMs'])
 def test_explicit_retract3_matches_conditioner_and_defaults2(self):
  self.assertEqual(M.derive(self.q,self.load,self.q['reviewedMs'])[0]['retractDegrees'],2)
  self.q['retractDegrees']=3
  e,_,_,t=M.derive(self.q,self.load,self.q['reviewedMs'])
  self.assertEqual(e['retractDegrees'],3);self.assertEqual(t['compensatedSequence']['retractDegrees'],3)
  self.assertEqual(t['compensatedSequence']['retractDwellMilliseconds'],500)
  for bad in (True,3.0,1,4,6):
   self.q['retractDegrees']=bad
   with self.assertRaises(ValueError):M.derive(self.q,self.load,self.q['reviewedMs'])
 def test_conditioning6_is_explicit_and_does_not_change_pad_dose(self):
  self.assertEqual(M.derive(self.q,self.load,self.q['reviewedMs'])[0]['conditioningDoseDegrees'],20)
  self.q['conditioningDoseDegrees']=6;self.q['doseDegrees']=12;self.q['retractDegrees']=3
  e,_,_,t=M.derive(self.q,self.load,self.q['reviewedMs'])
  self.assertEqual(e['conditioningDoseDegrees'],6);self.assertEqual(e['conditioningDwellMilliseconds'],2000)
  self.assertEqual(t['compensatedSequence']['doseDegrees'],12)
  for bad in (True,6.0,4,18):
   self.q['conditioningDoseDegrees']=bad
   with self.assertRaises(ValueError):M.derive(self.q,self.load,self.q['reviewedMs'])
 def test_conditioner12_and_explicit_restore3_are_bound(self):
  self.q.update(conditioningDoseDegrees=12,retractDegrees=3)
  e,_,_,_=M.derive(self.q,self.load,self.q['reviewedMs']);self.assertEqual(e['conditioningRestoreDegrees'],0)
  self.q['conditioningRestoreDegrees']=3
  e,_,_,t=M.derive(self.q,self.load,self.q['reviewedMs']);self.assertEqual(e['conditioningDoseDegrees'],12);self.assertEqual(e['conditioningRestoreDegrees'],3);self.assertEqual(t['compensatedSequence']['retractDegrees'],3)
  for bad in (True,3.0,2,6):
   self.q['conditioningRestoreDegrees']=bad
   with self.assertRaises(ValueError):M.derive(self.q,self.load,self.q['reviewedMs'])
  self.q.update(conditioningRestoreDegrees=3,conditioningDoseDegrees=6)
  with self.assertRaises(ValueError):M.derive(self.q,self.load,self.q['reviewedMs'])
 def test_final_dummy_wipe_requires_exact_reviewed_conditioner6_R3(self):
  self.assertEqual(M.derive(self.q,self.load,self.q['reviewedMs'])[0]['conditioningFinalWipeMm'],0)
  self.q.update(conditioningDoseDegrees=6,retractDegrees=3,conditioningFinalWipeMm=1.5)
  with self.assertRaises(ValueError):M.derive(self.q,self.load,self.q['reviewedMs'])
  self.q['attestations']['conditioningFinalWipeReviewed']=True
  e,r,_,_=M.derive(self.q,self.load,self.q['reviewedMs'])
  self.assertEqual(e['conditioningFinalWipeMm'],1.5);self.assertTrue(e['conditioningFinalWipeReviewed']);self.assertTrue(r['attestations']['conditioningFinalWipeReviewed'])
  for bad in (-1.5,1,2,True):
   self.q['conditioningFinalWipeMm']=bad
   with self.assertRaises(ValueError):M.derive(self.q,self.load,self.q['reviewedMs'])
 def test_rejects_missing_attestation_stale_review_wrong_start_surface_and_pair(self):
  edits=[lambda q:q['attestations'].update(tipReviewedNoLongStrand=False),lambda q:q.update(reviewedMs=q['reviewedMs']-300001),lambda q:q['startRaw'].update(B=-999),lambda q:q.update(surfaceRawZ=58.45),lambda q:q['pairReviews'][0].update(padsAvailableReviewed=False),lambda q:q['pairReviews'][1].update(reference='R1'),lambda q:q['pairReviews'][0].update(capturedMs=q['reviewedMs']+1)]
  for edit in edits:
   q=copy.deepcopy(self.q);edit(q)
   with self.assertRaises(ValueError):M.derive(q,self.load,self.q['reviewedMs'])
 def test_exclusive_output_hash_checks_and_disabled_preparer_only(self):
  inp=self.root/'inputs.json';inp.write_text(json.dumps(self.q));out=self.root/'out';calls=[]
  def run(cmd,**kwargs):calls.append(cmd);return SimpleNamespace(stdout='{"enabled":false,"motionDispatched":false}')
  with patch.object(M.subprocess,'run',side_effect=run):M.build(inp,out)
  self.assertEqual(Path(calls[0][1]).name,'prepare-conditioned-ftp-eight-pad.py');self.assertNotIn('dispatch',' '.join(calls[0]));self.assertEqual(json.loads((out/'clearance-review.json').read_text())['reviewedMs'],self.q['reviewedMs'])
  with self.assertRaises(FileExistsError):M.build(inp,out)
  failure=M.subprocess.CalledProcessError(2,['offline-preparer'],stderr='specific source hash mismatch')
  with patch.object(M.subprocess,'run',side_effect=failure):
   with self.assertRaisesRegex(ValueError,'specific source hash mismatch'):M.build(inp,self.root/'rejected')
  Path(self.q['sources']['surface']['path']).write_text('{}')
  with self.assertRaises(ValueError):M.build(inp,self.root/'changed')
if __name__=='__main__':unittest.main()
