import copy, importlib.util, json, tempfile, time, unittest
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
S=Path(__file__).with_name('author-conditioned-ftp-pair.py');spec=importlib.util.spec_from_file_location('author_pair',S);M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
class AuthorInputsTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  def write(n,v):
   p=self.root/n;p.write_bytes(v if isinstance(v,bytes) else json.dumps(v).encode());return M.PAIR.path_evidence(p)
  self.write=write;raw={'X':10,'Y':20,'Z':58.45,'A':720,'B':-1000};session={'sessionId':'test','jvmStartMs':1,'liveConfigurationSha256':'a'*64};self.raw=raw
  src={k:write(k+'.json',{}) for k in M.SOURCE_KEYS}
  src.update(template=write('template.json',session),barrier=write('barrier.json',{'afterQuerySnapshot':{'raw':raw}}),stationaryImage=write('stationary.jpg',b'\xff\xd8\xfftest'),tipImage=write('tip.jpg',b'\xff\xd8\xfftest'),surface=write('surface.json',{'surface':{'rawZ':58.3,'estimatedGapMm':.4,'gapUncertaintyMm':.3}}),tipOffset=write('tip.json',{'cameraMinusTipXYMm':[45.4,-64.49]}),scrapProfile=write('profile.json',{**session,'estimatedGapMm':.4,'gapUncertaintyMm':.3}),scrapExperiment=write('experiment.json',{'schema':1,'scope':'reviewed-scrap-retraction-coupon','mode':'transfer-preparation','startRaw':{'B':123},'workRawZ':58.45,'clearanceRawZ':53.45,'primeDegrees':60,'preWipeReliefDegrees':20,'conditioningDoseDegrees':20,'conditioningDwellMilliseconds':2000,'retractDegrees':2,'retractDwellMilliseconds':500}))
  src['registration']=write('registration.json',{'resistorPadMachineXYTargets':[{'padId':f'R{r}.{n}','machineXYMm':[100+r,200+n]} for r in range(1,5) for n in (1,2)]})
  now=int(time.time()*1000);report=write('camera.json',{'finishedAt':datetime.fromtimestamp((now-10)/1000,timezone.utc).isoformat()})
  self.q={'schema':1,'scope':'reviewed-pair-authoring-inputs','reviewedBy':'test reviewer','reviewedMs':now,'reviewBasis':'Explicit synthetic complete-route physical review','profileBasis':'Explicit synthetic gap basis, no precision calibration','startRaw':raw,'doseDegrees':6,'surfaceRawZ':58.3,'xyClearanceRawZ':53.4,'scrapTargetsXY':[{'X':11,'Y':20},{'X':12,'Y':21}],'attestations':{k:True for k in M.ATTESTATIONS},'sources':src,'pairReviews':[{'reference':f'R{r}','padIds':[f'R{r}.2',f'R{r}.1'],'padIdentityReviewed':True,'padsAvailableReviewed':True,'reportEvidence':report,'imageEvidence':src['stationaryImage'],'capturedMs':now-10} for r in range(1,2)]}
 def tearDown(self):self.temp.cleanup()
 def load(self,e,json_value=True):
  b=Path(e['path']).read_bytes();return json.loads(b) if json_value else b
 def test_derives_only_explicit_selection_preserves_inputs_and_pair_order(self):
  before=copy.deepcopy(self.q);e,r,p,t=M.derive(self.q,self.load,self.q['reviewedMs'])
  self.assertEqual(self.q,before);self.assertEqual(e['startRaw'],self.raw);self.assertEqual(e['primeDegrees'],60);self.assertEqual(t['reviewedMs'],self.q['reviewedMs']);self.assertEqual(r['reviewedMs'],self.q['reviewedMs']);self.assertEqual([x['padId'] for x in t['pads']][:2],['R1.2','R1.1']);self.assertEqual(t['pads'][0]['rawPose'],{'X':55.6,'Y':266.49,'Z':58.3,'A':720});self.assertEqual(p['estimatedGapMm'],.4);self.assertEqual(t['compensatedSequence']['doseDegrees'],6)
 def test_explicit_forward_dwell_defaults200_and_uses_existing_pair_range(self):
  original=copy.deepcopy(self.q)
  self.assertEqual(M.derive(self.q,self.load,self.q['reviewedMs'])[3]['compensatedSequence']['dwellMilliseconds'],200)
  for wait in (0,200,500,1000,2000):
   q=copy.deepcopy(original);q['dwellMilliseconds']=wait;e,_,_,t=M.derive(q,self.load,q['reviewedMs']);self.assertEqual(t['compensatedSequence']['dwellMilliseconds'],wait);self.assertEqual(e['conditioningDwellMilliseconds'],2000)
  for wait in (True,200.0,-1,2001):
   q=copy.deepcopy(original);q['dwellMilliseconds']=wait
   with self.assertRaises(ValueError):M.derive(q,self.load,q['reviewedMs'])
 def test_dose12_keeps_authored_conditioner_and_complete_pair_scope(self):
  self.q['doseDegrees']=12;self.q['dwellMilliseconds']=1000
  e,r,p,t=M.derive(self.q,self.load,self.q['reviewedMs'])
  self.assertEqual(e['conditioningDoseDegrees'],20)
  self.assertEqual(t['scope'],'ftp-two-pad-commissioning-targets')
  self.assertEqual(t['compensatedSequence']['doseDegrees'],12)
  self.assertEqual(t['compensatedSequence']['dwellMilliseconds'],1000)
  self.assertEqual(len(t['pads']),2)
  self.assertNotIn('pairReferences',t)
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
  for bad in (True,6.0,4,12):
   self.q['conditioningDoseDegrees']=bad
   with self.assertRaises(ValueError):M.derive(self.q,self.load,self.q['reviewedMs'])
 def test_rejects_missing_attestation_stale_review_wrong_start_surface_and_pair(self):
  edits=[lambda q:q['attestations'].update(tipReviewedNoLongStrand=False),lambda q:q.update(reviewedMs=q['reviewedMs']-300001),lambda q:q['startRaw'].update(B=-999),lambda q:q.update(surfaceRawZ=58.45),lambda q:q['pairReviews'][0].update(padsAvailableReviewed=False),lambda q:q['pairReviews'].append(copy.deepcopy(q['pairReviews'][0])),lambda q:q['pairReviews'][0].update(capturedMs=q['reviewedMs']+1)]
  for edit in edits:
   q=copy.deepcopy(self.q);edit(q)
   with self.assertRaises(ValueError):M.derive(q,self.load,self.q['reviewedMs'])
 def test_exclusive_output_hash_checks_and_disabled_preparer_only(self):
  inp=self.root/'inputs.json';inp.write_text(json.dumps(self.q));out=self.root/'out';calls=[]
  def run(cmd,**kwargs):calls.append(cmd);return SimpleNamespace(stdout='{"enabled":false,"motionDispatched":false}')
  with patch.object(M.subprocess,'run',side_effect=run):M.build(inp,out)
  self.assertEqual(Path(calls[0][1]).name,'prepare-conditioned-ftp-pair.py');self.assertNotIn('dispatch',' '.join(calls[0]));self.assertEqual(json.loads((out/'clearance-review.json').read_text())['reviewedMs'],self.q['reviewedMs'])
  with self.assertRaises(FileExistsError):M.build(inp,out)
  failure=M.subprocess.CalledProcessError(2,['offline-preparer'],stderr='specific source hash mismatch')
  with patch.object(M.subprocess,'run',side_effect=failure):
   with self.assertRaisesRegex(ValueError,'specific source hash mismatch'):M.build(inp,self.root/'rejected')
  Path(self.q['sources']['surface']['path']).write_text('{}')
  with self.assertRaises(ValueError):M.build(inp,self.root/'changed')
if __name__=='__main__':unittest.main()
